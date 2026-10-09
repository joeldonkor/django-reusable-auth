from django.db import models

# Create your models here.

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from .managers import CustomUserManager


class CustomUser(AbstractUser):
    username = None
    email = models.EmailField(_("email address"), unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        constraints = [
            # Backstop at the database level in case an email is saved without
            # going through the manager (e.g. via the admin or a raw update)
            models.UniqueConstraint(Lower("email"), name="unique_lower_email"),
        ]

    def __str__(self):
        return self.email