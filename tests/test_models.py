from django.contrib.auth import get_user_model
from django.test import TestCase

# Dynamically fetch the active User model
User = get_user_model()

class CustomUserModelTest(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            first_name="John",
            last_name="Doe",
            email="johndoe@example.com",
            password="securepassword123"
        )

        self.assertEqual(user.email, "johndoe@example.com")
        self.assertEqual(user.first_name, "John")
        self.assertEqual(user.last_name, "Doe")
        self.assertTrue(user.check_password("securepassword123"))


        