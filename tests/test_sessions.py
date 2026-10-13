from unittest import mock

import jwt
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from reusable_auth.checks import check_refresh_token_rotation
from reusable_auth.services import get_tokens_for_user

User = get_user_model()

NO_GRACE = override_settings(REUSABLE_AUTH={"REFRESH_TOKEN_REUSE_GRACE": 0})


class SessionTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email_verified=True, email="jane@example.com", password="securepassword123")
        self.laptop = get_tokens_for_user(self.user)
        self.phone = get_tokens_for_user(self.user)

    def refresh(self, token):
        return self.client.post(reverse("token-refresh"), {"refresh": token}, format="json")

    def auth(self, tokens=None):
        return {"HTTP_AUTHORIZATION": f"Bearer {(tokens or self.laptop)['access']}"}


# -----------------------------------------------------------------------------
# Refresh token reuse detection
# -----------------------------------------------------------------------------

@NO_GRACE
class ReuseDetectionTest(SessionTestCase):
    def test_reusing_a_rotated_token_revokes_every_session(self):
        rotated = self.refresh(self.laptop["refresh"]).data["refresh"]

        response = self.refresh(self.laptop["refresh"])  # replayed by an attacker
        self.assertEqual(response.status_code, 401)
        self.assertIn("WWW-Authenticate", response.headers)

        # Both the new token from the rotation and the other device are logged out
        self.assertEqual(self.refresh(rotated).status_code, 401)
        self.assertEqual(self.refresh(self.phone["refresh"]).status_code, 401)

    def test_attacker_refreshing_first_is_caught_when_real_user_refreshes(self):
        stolen_rotation = self.refresh(self.laptop["refresh"]).data["refresh"]  # attacker
        self.refresh(self.laptop["refresh"])  # real user, unaware
        self.assertEqual(self.refresh(stolen_rotation).status_code, 401)

    def test_logged_out_token_sent_again_is_just_rejected(self):
        # e.g. an app retrying a refresh after logout: not theft
        self.client.post(reverse("user-logout"), {"refresh": self.laptop["refresh"]}, format="json")
        self.assertEqual(self.refresh(self.laptop["refresh"]).status_code, 401)
        self.assertEqual(self.refresh(self.phone["refresh"]).status_code, 200)

    def test_revoked_device_refreshing_later_does_not_log_out_other_devices(self):
        # The user revokes a lost phone, which later tries to refresh
        session = OutstandingToken.objects.get(token=self.phone["refresh"])
        self.client.delete(reverse("session-detail", args=[session.id]), **self.auth())
        self.assertEqual(self.refresh(self.phone["refresh"]).status_code, 401)
        self.assertEqual(self.refresh(self.laptop["refresh"]).status_code, 200)

    def test_cleared_cache_skips_detection_but_still_rejects(self):
        self.refresh(self.laptop["refresh"])
        cache.clear()
        self.assertEqual(self.refresh(self.laptop["refresh"]).status_code, 401)
        self.assertEqual(self.refresh(self.phone["refresh"]).status_code, 200)

    def test_reuse_is_logged(self):
        self.refresh(self.laptop["refresh"])
        with self.assertLogs("reusable_auth.services", level="WARNING") as logs:
            self.refresh(self.laptop["refresh"])
        self.assertIn("Refresh token reuse detected", logs.output[0])

    def test_invalid_token_revokes_nothing(self):
        self.assertEqual(self.refresh("not-a-token").status_code, 401)
        self.assertEqual(self.refresh(self.phone["refresh"]).status_code, 200)

    def test_forged_token_with_a_real_jti_revokes_nothing(self):
        self.refresh(self.laptop["refresh"])  # laptop token is now blacklisted
        payload = jwt.decode(self.laptop["refresh"], options={"verify_signature": False})
        forged = jwt.encode(payload, "attacker-key-" + "x" * 32, algorithm="HS256")

        self.assertEqual(self.refresh(forged).status_code, 401)
        self.assertEqual(self.refresh(self.phone["refresh"]).status_code, 200)

    def test_access_token_sent_to_refresh_revokes_nothing(self):
        self.assertEqual(self.refresh(self.laptop["access"]).status_code, 401)
        self.assertEqual(self.refresh(self.phone["refresh"]).status_code, 200)

    def test_revocation_survives_atomic_requests(self):
        # With ATOMIC_REQUESTS, DRF rolls back the transaction when a view raises.
        # The view must return its 401 instead, or the revocation would be undone.
        self.refresh(self.laptop["refresh"])
        with mock.patch.dict(connection.settings_dict, {"ATOMIC_REQUESTS": True}):
            self.assertEqual(self.refresh(self.laptop["refresh"]).status_code, 401)
        self.assertEqual(self.refresh(self.phone["refresh"]).status_code, 401)


class ReuseGracePeriodTest(SessionTestCase):
    def test_concurrent_refresh_within_grace_period_is_not_treated_as_theft(self):
        # Two tabs refreshing at once: the second request arrives just after the first
        rotated = self.refresh(self.laptop["refresh"]).data["refresh"]
        self.assertEqual(self.refresh(self.laptop["refresh"]).status_code, 401)
        self.assertEqual(self.refresh(rotated).status_code, 200)
        self.assertEqual(self.refresh(self.phone["refresh"]).status_code, 200)


# -----------------------------------------------------------------------------
# Session management
# -----------------------------------------------------------------------------

class SessionListTest(SessionTestCase):
    url = reverse("session-list")

    def test_lists_one_session_per_device(self):
        response = self.client.get(self.url, **self.auth())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(set(response.data[0]), {"id", "issued_at", "expires_at"})

    def test_never_exposes_the_refresh_token(self):
        response = self.client.get(self.url, **self.auth())
        self.assertNotIn(self.laptop["refresh"], str(response.content))

    def test_rotation_does_not_add_sessions(self):
        self.refresh(self.laptop["refresh"])
        self.assertEqual(len(self.client.get(self.url, **self.auth()).data), 2)

    def test_excludes_logged_out_and_expired_sessions(self):
        self.client.post(reverse("user-logout"), {"refresh": self.laptop["refresh"]}, format="json")
        OutstandingToken.objects.filter(token=self.phone["refresh"]).update(expires_at="2000-01-01T00:00:00Z")
        self.assertEqual(self.client.get(self.url, **self.auth()).data, [])

    def test_only_lists_own_sessions(self):
        get_tokens_for_user(User.objects.create_user(email_verified=True, email="bob@example.com", password="securepassword123"))
        self.assertEqual(len(self.client.get(self.url, **self.auth()).data), 2)

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.client.delete(self.url).status_code, 401)

    def test_logout_everywhere(self):
        response = self.client.delete(self.url, **self.auth())
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.refresh(self.laptop["refresh"]).status_code, 401)
        self.assertEqual(self.refresh(self.phone["refresh"]).status_code, 401)


class SessionDetailTest(SessionTestCase):
    def url(self, tokens):
        session = OutstandingToken.objects.get(token=tokens["refresh"])
        return reverse("session-detail", args=[session.id])

    def test_revoke_one_session(self):
        response = self.client.delete(self.url(self.phone), **self.auth())
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.refresh(self.phone["refresh"]).status_code, 401)
        self.assertEqual(self.refresh(self.laptop["refresh"]).status_code, 200)

    def test_cannot_revoke_another_users_session(self):
        bob = get_tokens_for_user(User.objects.create_user(email_verified=True, email="bob@example.com", password="securepassword123"))
        response = self.client.delete(self.url(bob), **self.auth())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.refresh(bob["refresh"]).status_code, 200)

    def test_unknown_or_already_revoked_session_returns_404(self):
        url = self.url(self.phone)
        self.client.delete(url, **self.auth())
        self.assertEqual(self.client.delete(url, **self.auth()).status_code, 404)
        self.assertEqual(self.client.delete(reverse("session-detail", args=[999999]), **self.auth()).status_code, 404)


# -----------------------------------------------------------------------------
# System check
# -----------------------------------------------------------------------------

def test_rotation_disabled_warns():
    with override_settings(SIMPLE_JWT={"ROTATE_REFRESH_TOKENS": False}):
        assert [w.id for w in check_refresh_token_rotation(None)] == ["reusable_auth.W003"]


def test_rotation_enabled_passes():
    assert check_refresh_token_rotation(None) == []
