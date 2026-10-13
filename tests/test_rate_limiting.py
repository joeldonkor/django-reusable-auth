import time
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.checks import run_checks
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from reusable_auth.exceptions import AccountLocked, InvalidCredentials
from reusable_auth.security import _keys, unlock_account
from reusable_auth.services import login_user

User = get_user_model()

LOCKOUT_SETTINGS = {
    "LOGIN_MAX_FAILURES": 3,
    "LOGIN_FAILURE_WINDOW": 60,
    "LOGIN_LOCKOUT_DURATION": 60,
    "LOGIN_LOCKOUT_MAX_DURATION": 200,
    "LOGIN_LOCKOUT_RESET_AFTER": 60,
}


def drf_settings(**rates):
    return override_settings(REST_FRAMEWORK={"DEFAULT_THROTTLE_RATES": rates})


# -----------------------------------------------------------------------------
# Layer 1: IP throttling
# -----------------------------------------------------------------------------

class ThrottleTest(APITestCase):
    login_url = reverse("user-login")

    def login(self, ip="10.0.0.1", email="jane@example.com"):
        return self.client.post(
            self.login_url, {"email": email, "password": "wrongpassword"},
            format="json", REMOTE_ADDR=ip,
        )

    @drf_settings(auth_login="2/min")
    def test_login_is_throttled_per_ip(self):
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.login().status_code, 401)
        response = self.login()
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)

    @drf_settings(auth_login="1/min")
    def test_other_ips_are_not_affected(self):
        self.login(ip="10.0.0.1")
        self.assertEqual(self.login(ip="10.0.0.1").status_code, 429)
        self.assertEqual(self.login(ip="10.0.0.2").status_code, 401)

    @drf_settings(auth_login="1/min")
    def test_scopes_are_counted_separately(self):
        self.login()
        response = self.client.post(reverse("token-refresh"), {"refresh": "x"}, format="json", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(response.status_code, 401)  # refresh has its own budget

    @drf_settings(auth_register="1/hour")
    def test_register_is_throttled(self):
        url = reverse("user-register")
        self.client.post(url, {}, format="json")
        self.assertEqual(self.client.post(url, {}, format="json").status_code, 429)

    @drf_settings(auth_login=None)
    def test_rate_of_none_disables_throttle(self):
        # Above the 10/min default. A new email each time so the per-account
        # lockout (layer 2) doesn't kick in and hide what this test checks.
        for i in range(15):
            self.assertEqual(self.login(email=f"user{i}@example.com").status_code, 401)

    def test_default_rates_apply_without_settings(self):
        for _ in range(10):
            self.login()
        self.assertEqual(self.login().status_code, 429)


# -----------------------------------------------------------------------------
# Layer 2: account lockout
# -----------------------------------------------------------------------------

@override_settings(REUSABLE_AUTH=LOCKOUT_SETTINGS)
class LockoutServiceTest(TestCase):
    def setUp(self):
        User.objects.create_user(email_verified=True, email="jane@example.com", password="securepassword123")

    def fail(self, email="jane@example.com", times=1):
        for _ in range(times):
            with self.assertRaises(InvalidCredentials):
                login_user(email=email, password="wrongpassword")

    def test_account_locks_after_max_failures(self):
        self.fail(times=3)
        with self.assertRaises(AccountLocked):
            login_user(email="jane@example.com", password="wrongpassword")

    def test_locked_account_rejects_correct_password(self):
        self.fail(times=3)
        with self.assertRaises(AccountLocked):
            login_user(email="jane@example.com", password="securepassword123")

    def test_success_resets_failure_count(self):
        self.fail(times=2)
        login_user(email="jane@example.com", password="securepassword123")
        self.fail(times=2)
        login_user(email="jane@example.com", password="securepassword123")  # not locked

    def test_email_case_shares_one_counter(self):
        self.fail(email="jane@example.com")
        self.fail(email="JANE@example.com")
        self.fail(email="Jane@Example.com")
        with self.assertRaises(AccountLocked):
            login_user(email="jane@example.com", password="securepassword123")

    def test_unknown_email_locks_like_a_real_one(self):
        self.fail(email="nobody@example.com", times=3)
        with self.assertRaises(AccountLocked):
            login_user(email="nobody@example.com", password="wrongpassword")

    def test_lock_only_affects_that_account(self):
        User.objects.create_user(email_verified=True, email="bob@example.com", password="securepassword123")
        self.fail(times=3)
        login_user(email="bob@example.com", password="securepassword123")

    @override_settings(REUSABLE_AUTH={**LOCKOUT_SETTINGS, "LOGIN_LOCKOUT_DURATION": 1})
    def test_lock_expires(self):
        # Real waiting rather than mocking time, so this also holds on Redis,
        # which expires keys on its own clock
        self.fail(times=3)
        time.sleep(1.1)
        login_user(email="jane@example.com", password="securepassword123")

    def test_lockout_is_logged_without_the_email(self):
        with self.assertLogs("reusable_auth.security", level="WARNING") as logs:
            self.fail(times=3)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("Account locked", logs.output[0])
        self.assertNotIn("jane", logs.output[0])


@override_settings(REUSABLE_AUTH=LOCKOUT_SETTINGS)
class ProgressiveLockoutTest(TestCase):
    email = "jane@example.com"

    def setUp(self):
        User.objects.create_user(email_verified=True, email=self.email, password="securepassword123")

    def lock_and_get_duration(self):
        for _ in range(3):
            with self.assertRaises(InvalidCredentials):
                login_user(email=self.email, password="wrongpassword")
        with self.assertRaises(AccountLocked) as ctx:
            login_user(email=self.email, password="wrongpassword")
        # Simulate the lock running out, without waiting, but keep the lockout history
        cache.delete(_keys(self.email)[1])
        return ctx.exception.wait

    def test_each_lockout_doubles_up_to_the_max(self):
        durations = [self.lock_and_get_duration() for _ in range(4)]
        # Allow a second of slack for time passing during the test
        for actual, expected in zip(durations, [60, 120, 200, 200]):
            self.assertAlmostEqual(actual, expected, delta=1)

    def test_successful_login_resets_escalation(self):
        self.lock_and_get_duration()
        login_user(email=self.email, password="securepassword123")
        self.assertAlmostEqual(self.lock_and_get_duration(), 60, delta=1)


# -----------------------------------------------------------------------------
# Unlocking
# -----------------------------------------------------------------------------

@override_settings(REUSABLE_AUTH=LOCKOUT_SETTINGS)
class UnlockTest(TestCase):
    def setUp(self):
        User.objects.create_user(email_verified=True, email="jane@example.com", password="securepassword123")

    def lock(self):
        for _ in range(3):
            with self.assertRaises(InvalidCredentials):
                login_user(email="jane@example.com", password="wrongpassword")

    def test_unlock_account_allows_login(self):
        self.lock()
        self.assertTrue(unlock_account("JANE@example.com"))  # any casing works
        login_user(email="jane@example.com", password="securepassword123")

    def test_unlock_account_returns_false_when_not_locked(self):
        self.assertFalse(unlock_account("jane@example.com"))

    def test_management_command(self):
        self.lock()
        out = StringIO()
        call_command("unlock_account", "jane@example.com", "bob@example.com", stdout=out)
        self.assertIn("Unlocked jane@example.com", out.getvalue())
        self.assertIn("bob@example.com was not locked", out.getvalue())
        login_user(email="jane@example.com", password="securepassword123")


# -----------------------------------------------------------------------------
# System checks
# -----------------------------------------------------------------------------

def check_ids():
    return {message.id for message in run_checks()}


class SystemCheckTest(TestCase):
    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
    def test_dummy_cache_is_an_error(self):
        self.assertIn("reusable_auth.E001", check_ids())

    @override_settings(
        DEBUG=False,
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    )
    def test_locmem_cache_warns_in_production(self):
        self.assertIn("reusable_auth.W001", check_ids())

    @override_settings(
        DEBUG=True,
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    )
    def test_locmem_cache_is_fine_in_development(self):
        self.assertNotIn("reusable_auth.W001", check_ids())

    @override_settings(REUSABLE_AUTH={"LOGIN_MAX_FAILURE": 3})  # typo
    def test_unknown_setting_warns(self):
        self.assertIn("reusable_auth.W002", check_ids())


@override_settings(REUSABLE_AUTH=LOCKOUT_SETTINGS)
class LockoutViewTest(APITestCase):
    url = reverse("user-login")

    def test_locked_account_returns_429_with_retry_after(self):
        User.objects.create_user(email_verified=True, email="jane@example.com", password="securepassword123")
        for _ in range(3):
            self.client.post(self.url, {"email": "jane@example.com", "password": "wrongpassword"}, format="json")
        response = self.client.post(
            self.url, {"email": "jane@example.com", "password": "securepassword123"}, format="json"
        )
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("tokens", response.data)
        self.assertGreater(int(response.headers["Retry-After"]), 0)
