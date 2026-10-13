from django.contrib.auth.tokens import PasswordResetTokenGenerator, default_token_generator
from django.core.exceptions import ValidationError
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from reusable_auth.models import CustomUser


# -----------------------------------------------------------------------------
# One-time links (email verification, password reset)
# -----------------------------------------------------------------------------
#
# Each emailed link carries a uid (the user's id, base64-encoded) and a token.
# Nothing is stored in the database: the token is an HMAC, signed with
# SECRET_KEY, over the user's current state plus a timestamp. When that state
# changes the token no longer matches, which is what makes it single-use.
# Tokens expire after Django's PASSWORD_RESET_TIMEOUT (3 days by default).


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    # A different salt, so a password reset token can't be used to verify an
    # email and vice versa
    key_salt = "reusable_auth.tokens.EmailVerificationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        # Includes email_verified, so the link stops working once it's used,
        # and the email, so it stops working if the address changes
        return f"{user.pk}{user.email}{user.email_verified}{timestamp}"


email_verification_token = EmailVerificationTokenGenerator()

# Django's own generator: its hash includes the password hash and last_login, so
# a reset link stops working once the password changes or the user logs in
password_reset_token = default_token_generator


def encode_uid(user):
    return urlsafe_base64_encode(force_bytes(user.pk))


def get_user_from_link(uid, token, generator):
    """Return the user the link was issued for, or None if it's invalid or expired."""
    try:
        pk = urlsafe_base64_decode(uid).decode()
        user = CustomUser.objects.get(pk=pk)
    except (TypeError, ValueError, OverflowError, ValidationError, CustomUser.DoesNotExist):
        return None
    return user if generator.check_token(user, token) else None
