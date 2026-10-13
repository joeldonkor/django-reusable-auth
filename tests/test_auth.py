from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from reusable_auth.exceptions import InvalidCredentials
from reusable_auth.serializers import UserLoginSerializer, UserRegistrationSerializer, UserSerializer
from reusable_auth.services import get_tokens_for_user, login_user, register_user

User = get_user_model()

VALID_REGISTRATION = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "johndoe@example.com",
    "password": "securepassword123",
}


# -----------------------------------------------------------------------------
# Manager
# -----------------------------------------------------------------------------

class CustomUserManagerTest(TestCase):
    def test_create_user_normalizes_email_and_hashes_password(self):
        user = User.objects.create_user(email="jane@EXAMPLE.COM", password="securepassword123")
        self.assertEqual(user.email, "jane@example.com")
        self.assertNotEqual(user.password, "securepassword123")
        self.assertTrue(user.check_password("securepassword123"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertIsNone(getattr(user, "username", None))

    def test_create_user_without_email_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="securepassword123")

    def test_create_superuser(self):
        admin = User.objects.create_superuser(email="admin@example.com", password="securepassword123")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_active)

    def test_create_superuser_rejects_non_staff(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(email="admin@example.com", password="pw12345678", is_staff=False)
        with self.assertRaises(ValueError):
            User.objects.create_superuser(email="admin@example.com", password="pw12345678", is_superuser=False)

    def test_create_user_lowercases_whole_email(self):
        user = User.objects.create_user(email="  Jane.Doe@Example.com ", password="securepassword123")
        self.assertEqual(user.email, "jane.doe@example.com")

    def test_emails_differing_only_by_case_are_duplicates(self):
        User.objects.create_user(email="jane@example.com", password="securepassword123")
        with self.assertRaises(IntegrityError):
            User.objects.create_user(email="JANE@example.com", password="securepassword123")

    def test_db_constraint_blocks_case_variant_saved_without_manager(self):
        User.objects.create_user(email="jane@example.com", password="securepassword123")
        with self.assertRaises(IntegrityError):
            User(email="JANE@example.com").save()

    def test_str_returns_email(self):
        user = User.objects.create_user(email="jane@example.com", password="securepassword123")
        self.assertEqual(str(user), "jane@example.com")


# -----------------------------------------------------------------------------
# Serializers
# -----------------------------------------------------------------------------

class SerializerTest(TestCase):
    def test_registration_serializer_valid(self):
        self.assertTrue(UserRegistrationSerializer(data=VALID_REGISTRATION).is_valid())

    def test_registration_serializer_rejects_short_password_and_bad_email(self):
        serializer = UserRegistrationSerializer(
            data={**VALID_REGISTRATION, "email": "not-an-email", "password": "short"}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)
        self.assertIn("password", serializer.errors)

    def test_registration_serializer_requires_all_fields(self):
        serializer = UserRegistrationSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors), {"first_name", "last_name", "email", "password"})

    def test_registration_serializer_rejects_common_password(self):
        serializer = UserRegistrationSerializer(data={**VALID_REGISTRATION, "password": "password123"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)

    def test_registration_serializer_rejects_numeric_password(self):
        serializer = UserRegistrationSerializer(data={**VALID_REGISTRATION, "password": "8364927163"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)

    def test_registration_serializer_rejects_password_similar_to_email(self):
        serializer = UserRegistrationSerializer(data={**VALID_REGISTRATION, "password": "johndoe@example"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)

    def test_user_serializer_does_not_expose_password(self):
        user = User.objects.create_user(email="jane@example.com", password="securepassword123")
        self.assertNotIn("password", UserSerializer(user).data)

    def test_login_serializer_requires_email_and_password(self):
        serializer = UserLoginSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors), {"email", "password"})


# -----------------------------------------------------------------------------
# Services
# -----------------------------------------------------------------------------

class ServicesTest(TestCase):
    def test_register_user_creates_user(self):
        user = register_user(**VALID_REGISTRATION)
        self.assertEqual(user.email, "johndoe@example.com")
        self.assertEqual(user.first_name, "John")
        self.assertTrue(User.objects.filter(email="johndoe@example.com").exists())

    def test_register_user_hashes_password(self):
        user = register_user(**VALID_REGISTRATION)
        self.assertNotEqual(user.password, VALID_REGISTRATION["password"])
        self.assertTrue(user.check_password(VALID_REGISTRATION["password"]))

    def test_register_user_rejects_duplicate_email(self):
        register_user(**VALID_REGISTRATION)
        with self.assertRaises(ValueError):
            register_user(**VALID_REGISTRATION)
        self.assertEqual(User.objects.count(), 1)

    def test_register_user_rejects_duplicate_email_with_different_case(self):
        register_user(**VALID_REGISTRATION)
        with self.assertRaises(ValueError):
            register_user(**{**VALID_REGISTRATION, "email": "JohnDoe@Example.com"})
        self.assertEqual(User.objects.count(), 1)

    def test_login_user_is_case_insensitive(self):
        User.objects.create_user(email="jane@example.com", password="securepassword123")
        user = login_user(email="Jane@EXAMPLE.com", password="securepassword123")
        self.assertEqual(user.email, "jane@example.com")

    def test_login_user_with_valid_credentials(self):
        User.objects.create_user(email="jane@example.com", password="securepassword123")
        user = login_user(email="jane@example.com", password="securepassword123")
        self.assertEqual(user.email, "jane@example.com")

    def test_login_user_with_wrong_password_raises(self):
        User.objects.create_user(email="jane@example.com", password="securepassword123")
        with self.assertRaises(InvalidCredentials):
            login_user(email="jane@example.com", password="wrongpassword")

    def test_login_user_with_unknown_email_raises(self):
        with self.assertRaises(InvalidCredentials):
            login_user(email="nobody@example.com", password="securepassword123")

    def test_login_user_inactive_user_raises(self):
        User.objects.create_user(email="jane@example.com", password="securepassword123", is_active=False)
        with self.assertRaises(InvalidCredentials):
            login_user(email="jane@example.com", password="securepassword123")

    def test_get_tokens_for_user_returns_tokens_for_that_user(self):
        user = User.objects.create_user(email="jane@example.com", password="securepassword123")
        tokens = get_tokens_for_user(user)
        self.assertEqual(set(tokens), {"refresh", "access"})
        self.assertEqual(str(AccessToken(tokens["access"])["user_id"]), str(user.id))
        self.assertEqual(str(RefreshToken(tokens["refresh"])["user_id"]), str(user.id))


# -----------------------------------------------------------------------------
# API endpoints
# -----------------------------------------------------------------------------

class RegisterViewTest(APITestCase):
    url = reverse("user-register")

    def test_register_success_creates_user_without_returning_tokens(self):
        response = self.client.post(self.url, VALID_REGISTRATION, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("tokens", response.data)
        self.assertTrue(User.objects.filter(email="johndoe@example.com").exists())

    def test_register_invalid_payload_returns_400(self):
        response = self.client.post(self.url, {"email": "bad"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), 0)

    def test_register_duplicate_email_is_indistinguishable_from_new_email(self):
        new = self.client.post(self.url, VALID_REGISTRATION, format="json")
        duplicate = self.client.post(self.url, {**VALID_REGISTRATION, "email": "JOHNDOE@example.com"}, format="json")
        self.assertEqual(duplicate.status_code, new.status_code)
        self.assertEqual(duplicate.data, new.data)
        self.assertEqual(User.objects.count(), 1)

    def test_register_duplicate_does_not_change_existing_password(self):
        User.objects.create_user(email="johndoe@example.com", password="originalpassword99")
        self.client.post(self.url, VALID_REGISTRATION, format="json")
        self.assertTrue(User.objects.get().check_password("originalpassword99"))

    def test_register_weak_password_returns_400(self):
        response = self.client.post(self.url, {**VALID_REGISTRATION, "password": "password123"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)
        self.assertEqual(User.objects.count(), 0)

    def test_registered_user_can_log_in(self):
        self.client.post(self.url, VALID_REGISTRATION, format="json")
        response = self.client.post(
            reverse("user-login"),
            {"email": VALID_REGISTRATION["email"], "password": VALID_REGISTRATION["password"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)


class LoginViewTest(APITestCase):
    url = reverse("user-login")

    def setUp(self):
        self.user = User.objects.create_user(email="jane@example.com", password="securepassword123")

    def test_login_success_returns_tokens(self):
        response = self.client.post(
            self.url, {"email": "jane@example.com", "password": "securepassword123"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), {"access", "refresh"})

    def test_login_wrong_password_returns_401(self):
        response = self.client.post(
            self.url, {"email": "jane@example.com", "password": "wrongpassword"}, format="json"
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["detail"], "Invalid email or password.")

    def test_login_missing_fields_returns_400(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_login_updates_last_login(self):
        self.assertIsNone(self.user.last_login)
        self.client.post(self.url, {"email": "jane@example.com", "password": "securepassword123"}, format="json")
        self.user.refresh_from_db()
        # UPDATE_LAST_LOGIN in SIMPLE_JWT only applies to simplejwt's own views,
        # so this documents whether the custom login view records logins.
        self.assertIsNotNone(self.user.last_login)


class RefreshViewTest(APITestCase):
    url = reverse("token-refresh")

    def setUp(self):
        self.user = User.objects.create_user(email="jane@example.com", password="securepassword123")
        self.tokens = get_tokens_for_user(self.user)

    def test_refresh_returns_new_access_and_rotated_refresh(self):
        response = self.client.post(self.url, {"refresh": self.tokens["refresh"]}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)  # ROTATE_REFRESH_TOKENS=True

    def test_old_refresh_token_is_blacklisted_after_rotation(self):
        self.client.post(self.url, {"refresh": self.tokens["refresh"]}, format="json")
        response = self.client.post(self.url, {"refresh": self.tokens["refresh"]}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_invalid_refresh_token_returns_401(self):
        response = self.client.post(self.url, {"refresh": "not-a-token"}, format="json")
        self.assertEqual(response.status_code, 401)
