from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _


class CustomUserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifiers
    for authentication instead of usernames.
    """
    @classmethod
    def normalize_email(cls, email):
        """
        Lowercase the whole address (Django only lowercases the domain) so
        "John@x.com" and "john@x.com" are treated as the same account.
        """
        return (email or "").strip().lower()

    def get_by_natural_key(self, email):
        # Used by authenticate(), so login is case-insensitive too
        return self.get(**{self.model.USERNAME_FIELD: self.normalize_email(email)})

    def create_user(self, email, password, **extra_fields):
        """
        Create and save a user with the given email and password.
        """
        if not email:
            raise ValueError(_("The Email must be set"))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        # Created from the command line by someone with server access, so there's
        # no inbox to verify and no way to log in through the API otherwise
        extra_fields.setdefault("email_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        return self.create_user(email, password, **extra_fields)
