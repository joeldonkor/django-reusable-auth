from unittest import mock

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.test import APITestCase
from rest_framework.views import APIView

from reusable_auth.checks import check_token_blacklist_installed
from reusable_auth.services import get_tokens_for_user

User = get_user_model()

CREDENTIALS = {"email": "jane@example.com", "password": "securepassword123"}


# -----------------------------------------------------------------------------
# Logout
# -----------------------------------------------------------------------------

class LogoutViewTest(APITestCase):
    url = reverse("user-logout")

    def setUp(self):
        self.user = User.objects.create_user(**CREDENTIALS)
        self.tokens = get_tokens_for_user(self.user)

    def test_logout_blacklists_refresh_token(self):
        response = self.client.post(self.url, {"refresh": self.tokens["refresh"]}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"detail": "Logged out."})

        refresh = self.client.post(reverse("token-refresh"), {"refresh": self.tokens["refresh"]}, format="json")
        self.assertEqual(refresh.status_code, 401)

    def test_logout_does_not_need_an_access_token(self):
        # Access tokens have often expired by the time a user logs out
        response = self.client.post(self.url, {"refresh": self.tokens["refresh"]}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_logout_with_invalid_token_returns_401(self):
        response = self.client.post(self.url, {"refresh": "not-a-token"}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertIn("detail", response.data)

    def test_logout_rejects_access_token(self):
        response = self.client.post(self.url, {"refresh": self.tokens["access"]}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_logout_requires_refresh_field(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("refresh", response.data)

    def test_logout_only_revokes_that_session(self):
        other = get_tokens_for_user(self.user)  # e.g. logged in on another device
        self.client.post(self.url, {"refresh": self.tokens["refresh"]}, format="json")
        response = self.client.post(reverse("token-refresh"), {"refresh": other["refresh"]}, format="json")
        self.assertEqual(response.status_code, 200)


# -----------------------------------------------------------------------------
# Current user
# -----------------------------------------------------------------------------

class CurrentUserViewTest(APITestCase):
    url = reverse("current-user")

    def setUp(self):
        self.user = User.objects.create_user(first_name="Jane", **CREDENTIALS)
        self.access = get_tokens_for_user(self.user)["access"]

    def test_returns_current_user(self):
        response = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {self.access}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "jane@example.com")
        self.assertEqual(response.data["first_name"], "Jane")
        self.assertNotIn("password", response.data)

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)
        self.assertIn("detail", response.data)

    def test_rejects_invalid_token(self):
        response = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer not-a-token")
        self.assertEqual(response.status_code, 401)

    def test_rejects_refresh_token(self):
        refresh = get_tokens_for_user(self.user)["refresh"]
        response = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {refresh}")
        self.assertEqual(response.status_code, 401)


# -----------------------------------------------------------------------------
# Independence from the host project's DRF defaults
# -----------------------------------------------------------------------------

class HostDefaultsTest(APITestCase):
    """
    Simulates a host project with strict REST_FRAMEWORK defaults.

    override_settings can't do this: DRF copies DEFAULT_AUTHENTICATION_CLASSES and
    DEFAULT_PERMISSION_CLASSES onto APIView when it's first imported. So patch
    APIView itself, which is what every view without its own classes inherits.
    """

    def setUp(self):
        User.objects.create_user(**CREDENTIALS)
        for name, value in [
            ("authentication_classes", [SessionAuthentication]),
            ("permission_classes", [IsAuthenticated]),
        ]:
            patcher = mock.patch.object(APIView, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_public_endpoints_work_when_host_requires_authentication(self):
        register = self.client.post(
            reverse("user-register"),
            {"first_name": "Bob", "last_name": "Doe", "email": "bob@example.com", "password": "securepassword123"},
            format="json",
        )
        self.assertEqual(register.status_code, 201)
        login = self.client.post(reverse("user-login"), CREDENTIALS, format="json")
        self.assertEqual(login.status_code, 200)

    def test_me_uses_jwt_even_when_host_uses_sessions(self):
        access = self.client.post(reverse("user-login"), CREDENTIALS, format="json").data["access"]
        response = self.client.get(reverse("current-user"), HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(response.status_code, 200)

    def test_stale_bearer_header_does_not_block_login(self):
        response = self.client.post(
            reverse("user-login"), CREDENTIALS, format="json", HTTP_AUTHORIZATION="Bearer expired-or-garbage",
        )
        self.assertEqual(response.status_code, 200)


# -----------------------------------------------------------------------------
# Error format
# -----------------------------------------------------------------------------

class ErrorFormatTest(APITestCase):
    def test_validation_errors_are_keyed_by_field(self):
        response = self.client.post(reverse("user-login"), {"email": "bad"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data), {"email", "password"})

    def test_non_field_errors_use_detail(self):
        for url, data in [
            (reverse("user-login"), {"email": "nobody@example.com", "password": "wrongpassword"}),
            (reverse("token-refresh"), {"refresh": "bad"}),
            (reverse("user-logout"), {"refresh": "bad"}),
        ]:
            response = self.client.post(url, data, format="json")
            self.assertEqual(response.status_code, 401, url)
            self.assertIn("detail", response.data, url)


# -----------------------------------------------------------------------------
# System check
# -----------------------------------------------------------------------------

def test_missing_token_blacklist_app_is_an_error():
    with mock.patch("reusable_auth.checks.apps.is_installed", return_value=False):
        assert [e.id for e in check_token_blacklist_installed(None)] == ["reusable_auth.E002"]


def test_installed_token_blacklist_app_passes():
    assert check_token_blacklist_installed(None) == []
