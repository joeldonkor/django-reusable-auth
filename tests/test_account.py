import importlib
import re

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from reusable_auth.checks import check_email_link_urls, check_email_templates
from reusable_auth.security import record_failed_login
from reusable_auth.services import get_tokens_for_user
from reusable_auth.tokens import encode_uid, password_reset_token

User = get_user_model()

PASSWORD = "securepassword123"
NEW_PASSWORD = "brand-new-passphrase-42"

LINK_SETTINGS = {
    "EMAIL_VERIFICATION_URL": "https://app.test/verify?uid={uid}&token={token}",
    "PASSWORD_RESET_URL": "https://app.test/reset?uid={uid}&token={token}",
}
LINKS = override_settings(REUSABLE_AUTH=LINK_SETTINGS)

REGISTRATION = {"first_name": "Jane", "last_name": "Doe", "email": "jane@example.com", "password": PASSWORD}


def link_params(email):
    """The uid and token from the link in an email."""
    match = re.search(r"\?uid=([^&\s]+)&token=(\S+)", email.body)
    return {"uid": match[1], "token": match[2]}


def failing_sender(kind, user, context):
    raise ConnectionRefusedError("SMTP server is down")


def recording_sender(kind, user, context):
    recording_sender.calls.append((kind, user.email, sorted(context)))


recording_sender.calls = []


# -----------------------------------------------------------------------------
# Email verification
# -----------------------------------------------------------------------------

@LINKS
class EmailVerificationTest(APITestCase):
    def login(self, password=PASSWORD):
        return self.client.post(reverse("user-login"), {"email": "jane@example.com", "password": password}, format="json")

    def register(self, data=REGISTRATION):
        return self.client.post(reverse("user-register"), data, format="json")

    def test_full_flow_register_verify_login(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertIn("Check your email", response.data["detail"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["jane@example.com"])
        self.assertEqual(mail.outbox[0].subject, "Verify your email address")

        blocked = self.login()
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.data["detail"].code, "email_not_verified")

        verified = self.client.post(reverse("email-verify"), link_params(mail.outbox[0]), format="json")
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(self.login().status_code, 200)

    def test_link_is_not_html_escaped_in_plain_text_email(self):
        self.register()
        self.assertIn("&token=", mail.outbox[0].body)
        self.assertNotIn("&amp;", mail.outbox[0].body)

    def test_verification_link_works_once(self):
        self.register()
        params = link_params(mail.outbox[0])
        self.client.post(reverse("email-verify"), params, format="json")
        response = self.client.post(reverse("email-verify"), params, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"].code, "invalid_link")

    def test_invalid_links_are_rejected(self):
        self.register()
        uid = link_params(mail.outbox[0])["uid"]
        for params in [{"uid": uid, "token": "wrong"}, {"uid": "garbage", "token": "x"}, {"uid": "", "token": ""}]:
            response = self.client.post(reverse("email-verify"), params, format="json")
            self.assertEqual(response.status_code, 400, params)
        self.assertFalse(User.objects.get().email_verified)

    def test_password_reset_token_cannot_verify_email(self):
        user = User.objects.create_user(email="jane@example.com", password=PASSWORD)
        params = {"uid": encode_uid(user), "token": password_reset_token.make_token(user)}
        self.assertEqual(self.client.post(reverse("email-verify"), params, format="json").status_code, 400)

    def test_unverified_user_with_wrong_password_gets_401_not_403(self):
        # Revealing "not verified" is only safe once the password is known to be right
        User.objects.create_user(email="jane@example.com", password=PASSWORD)
        self.assertEqual(self.login(password="wrongpassword").status_code, 401)

    def test_duplicate_registration_emails_the_existing_owner(self):
        User.objects.create_user(email="jane@example.com", password="original-password-1", email_verified=True)
        response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertIn("Check your email", response.data["detail"])  # same as a new signup
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Someone tried to sign up with your email")

    @override_settings(REUSABLE_AUTH={**LINK_SETTINGS, "REQUIRE_EMAIL_VERIFICATION": False})
    def test_verification_off_sends_nothing_and_allows_login(self):
        self.register()
        self.assertEqual(mail.outbox, [])
        self.assertEqual(self.login().status_code, 200)

    @override_settings(REUSABLE_AUTH={})
    def test_without_link_setting_email_contains_raw_code(self):
        self.register()
        self.assertIn("uid: ", mail.outbox[0].body)
        self.assertIn("token: ", mail.outbox[0].body)


@LINKS
class ResendVerificationTest(APITestCase):
    url = reverse("email-verify-resend")

    def resend(self, email="jane@example.com"):
        return self.client.post(self.url, {"email": email}, format="json")

    def test_sends_to_unverified_user(self):
        User.objects.create_user(email="jane@example.com", password=PASSWORD)
        self.assertEqual(self.resend().status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    def test_same_response_for_verified_unknown_and_unverified(self):
        User.objects.create_user(email="jane@example.com", password=PASSWORD)
        User.objects.create_user(email="bob@example.com", password=PASSWORD, email_verified=True)
        responses = [self.resend(email) for email in ["jane@example.com", "bob@example.com", "nobody@example.com"]]
        self.assertEqual({r.status_code for r in responses}, {200})
        self.assertEqual(len({r.data["detail"] for r in responses}), 1)
        self.assertEqual(len(mail.outbox), 1)  # only jane

    def test_cooldown_stops_flooding_one_inbox(self):
        User.objects.create_user(email="jane@example.com", password=PASSWORD)
        self.resend()
        self.resend(email="JANE@example.com")
        self.assertEqual(len(mail.outbox), 1)


# -----------------------------------------------------------------------------
# Email sending
# -----------------------------------------------------------------------------

@override_settings(REUSABLE_AUTH={**LINK_SETTINGS, "EMAIL_SENDER": "tests.test_account.failing_sender"})
class EmailFailureTest(APITestCase):
    def test_mail_failure_does_not_reveal_which_emails_exist(self):
        User.objects.create_user(email="jane@example.com", password=PASSWORD, email_verified=True)
        url = reverse("password-reset")
        with self.assertLogs("reusable_auth.emails", level="ERROR"):
            known = self.client.post(url, {"email": "jane@example.com"}, format="json")
        unknown = self.client.post(url, {"email": "nobody@example.com"}, format="json")
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.data, unknown.data)


@override_settings(REUSABLE_AUTH={**LINK_SETTINGS, "EMAIL_SENDER": "tests.test_account.recording_sender"})
class CustomSenderTest(APITestCase):
    def test_custom_sender_receives_kind_user_and_context(self):
        recording_sender.calls.clear()
        self.client.post(reverse("user-register"), REGISTRATION, format="json")
        self.assertEqual(recording_sender.calls, [("verify_email", "jane@example.com", ["link", "token", "uid", "user"])])
        self.assertEqual(mail.outbox, [])


# -----------------------------------------------------------------------------
# Password reset
# -----------------------------------------------------------------------------

@LINKS
class PasswordResetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="jane@example.com", password=PASSWORD, email_verified=True)

    def request_reset(self, email="jane@example.com"):
        return self.client.post(reverse("password-reset"), {"email": email}, format="json")

    def confirm(self, params, password=NEW_PASSWORD):
        return self.client.post(reverse("password-reset-confirm"), {**params, "new_password": password}, format="json")

    def test_same_response_for_known_and_unknown_email(self):
        known, unknown = self.request_reset(), self.request_reset("nobody@example.com")
        self.assertEqual((known.status_code, known.data), (unknown.status_code, unknown.data))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Reset your password")

    def test_reset_sets_new_password_and_logs_out_everywhere(self):
        old_session = get_tokens_for_user(self.user)
        self.request_reset()
        response = self.confirm(link_params(mail.outbox[0]))
        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        refresh = self.client.post(reverse("token-refresh"), {"refresh": old_session["refresh"]}, format="json")
        self.assertEqual(refresh.status_code, 401)
        self.assertEqual(mail.outbox[-1].subject, "Your password was changed")

    def test_reset_link_works_once(self):
        self.request_reset()
        params = link_params(mail.outbox[0])
        self.confirm(params)
        self.assertEqual(self.confirm(params, password="another-passphrase-77").status_code, 400)

    def test_weak_password_is_rejected_and_link_still_works(self):
        self.request_reset()
        params = link_params(mail.outbox[0])
        weak = self.confirm(params, password="password123")
        self.assertEqual(weak.status_code, 400)
        self.assertIn("new_password", weak.data)
        self.assertEqual(self.confirm(params).status_code, 200)

    def test_invalid_link_is_rejected(self):
        self.assertEqual(self.confirm({"uid": encode_uid(self.user), "token": "wrong"}).status_code, 400)

    def test_reset_verifies_email_and_clears_lockout(self):
        User.objects.filter(pk=self.user.pk).update(email_verified=False)
        for _ in range(5):
            record_failed_login("jane@example.com")  # someone locked the account
        self.request_reset()
        self.confirm(link_params(mail.outbox[0]))

        login = self.client.post(reverse("user-login"), {"email": "jane@example.com", "password": NEW_PASSWORD}, format="json")
        self.assertEqual(login.status_code, 200)

    def test_no_email_for_deactivated_account(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.request_reset()
        self.assertEqual(mail.outbox, [])


# -----------------------------------------------------------------------------
# Password change
# -----------------------------------------------------------------------------

class PasswordChangeTest(APITestCase):
    url = reverse("password-change")

    def setUp(self):
        self.user = User.objects.create_user(email="jane@example.com", password=PASSWORD, email_verified=True)
        self.tokens = get_tokens_for_user(self.user)
        self.other_device = get_tokens_for_user(self.user)

    def change(self, old=PASSWORD, new=NEW_PASSWORD):
        return self.client.post(
            self.url, {"old_password": old, "new_password": new}, format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.tokens['access']}",
        )

    def refresh(self, token):
        return self.client.post(reverse("token-refresh"), {"refresh": token}, format="json")

    def test_change_password_logs_out_other_sessions_and_returns_new_tokens(self):
        response = self.change()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), {"access", "refresh"})

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertEqual(self.refresh(self.tokens["refresh"]).status_code, 401)
        self.assertEqual(self.refresh(self.other_device["refresh"]).status_code, 401)
        self.assertEqual(self.refresh(response.data["refresh"]).status_code, 200)
        self.assertEqual(mail.outbox[-1].subject, "Your password was changed")

    def test_wrong_old_password(self):
        response = self.change(old="wrongpassword")
        self.assertEqual(response.status_code, 400)
        self.assertIn("old_password", response.data)
        self.assertEqual(self.refresh(self.other_device["refresh"]).status_code, 200)

    def test_weak_new_password(self):
        response = self.change(new="password123")
        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password", response.data)

    def test_requires_authentication(self):
        response = self.client.post(self.url, {"old_password": PASSWORD, "new_password": NEW_PASSWORD}, format="json")
        self.assertEqual(response.status_code, 401)


# -----------------------------------------------------------------------------
# Account deactivation
# -----------------------------------------------------------------------------

class DeactivationTest(APITestCase):
    url = reverse("account-deactivate")

    def setUp(self):
        self.user = User.objects.create_user(email="jane@example.com", password=PASSWORD, email_verified=True)
        self.tokens = get_tokens_for_user(self.user)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.tokens['access']}"}

    def test_deactivate_ends_everything(self):
        response = self.client.post(self.url, {"password": PASSWORD}, format="json", **self.auth)
        self.assertEqual(response.status_code, 204)

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        refresh = self.client.post(reverse("token-refresh"), {"refresh": self.tokens["refresh"]}, format="json")
        self.assertEqual(refresh.status_code, 401)
        self.assertEqual(self.client.get(reverse("current-user"), **self.auth).status_code, 401)
        login = self.client.post(reverse("user-login"), {"email": "jane@example.com", "password": PASSWORD}, format="json")
        self.assertEqual(login.status_code, 401)

    def test_wrong_password_keeps_account(self):
        response = self.client.post(self.url, {"password": "wrongpassword"}, format="json", **self.auth)
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_reactivation_does_not_revive_old_sessions(self):
        # e.g. an admin unticks "active" in the Django admin, then ticks it again.
        # simplejwt rejects an inactive user's tokens, but only while inactive.
        self.user.is_active = False
        self.user.save()
        self.user.is_active = True
        self.user.save()
        refresh = self.client.post(reverse("token-refresh"), {"refresh": self.tokens["refresh"]}, format="json")
        self.assertEqual(refresh.status_code, 401)


# -----------------------------------------------------------------------------
# Users, migration and checks
# -----------------------------------------------------------------------------

class UserTest(TestCase):
    def test_new_users_are_unverified(self):
        self.assertFalse(User.objects.create_user(email="jane@example.com", password=PASSWORD).email_verified)

    def test_superusers_are_verified(self):
        self.assertTrue(User.objects.create_superuser(email="admin@example.com", password=PASSWORD).email_verified)

    def test_migration_marks_existing_users_verified(self):
        User.objects.create_user(email="jane@example.com", password=PASSWORD)
        migration = importlib.import_module("reusable_auth.migrations.0002_email_verified")
        migration.mark_existing_users_verified(apps, None)
        self.assertTrue(User.objects.get().email_verified)


class EmailCheckTest(TestCase):
    @override_settings(TEMPLATES=[])
    def test_missing_templates_is_an_error(self):
        self.assertEqual([e.id for e in check_email_templates(None)], ["reusable_auth.E003"])

    @override_settings(TEMPLATES=[], REUSABLE_AUTH={"EMAIL_SENDER": "tests.test_account.recording_sender"})
    def test_custom_sender_does_not_need_templates(self):
        self.assertEqual(check_email_templates(None), [])

    @override_settings(REUSABLE_AUTH={})
    def test_missing_link_urls_warn(self):
        self.assertEqual([w.id for w in check_email_link_urls(None)], ["reusable_auth.W004"] * 2)

    @override_settings(REUSABLE_AUTH={**LINK_SETTINGS})
    def test_link_urls_set(self):
        self.assertEqual(check_email_link_urls(None), [])
