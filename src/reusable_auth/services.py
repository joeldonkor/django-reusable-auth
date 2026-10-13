import logging
import time

from rest_framework_simplejwt.exceptions import TokenBackendError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.state import token_backend
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import serializers
from reusable_auth.conf import get_setting
from reusable_auth.emails import send_password_changed_email
from reusable_auth.exceptions import EmailNotVerified, InvalidCredentials, InvalidLink
from reusable_auth.models import CustomUser
from reusable_auth.security import check_not_locked, record_failed_login, reset_failed_logins, unlock_account
from reusable_auth.tokens import email_verification_token, get_user_from_link, password_reset_token
from django.db import IntegrityError, transaction
from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Tokens
# -----------------------------------------------------------------------------

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


# -----------------------------------------------------------------------------
# User registration & login
# -----------------------------------------------------------------------------

@transaction.atomic
def register_user(first_name, last_name, email, password):
    email = CustomUser.objects.normalize_email(email)
    if CustomUser.objects.filter(email=email).exists():
        raise ValueError("A user with this email already exists.")

    try:
        # create_user hashes the password; create() would store it as plain text
        user = CustomUser.objects.create_user(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password
        )
    except IntegrityError:
        # Another request registered the same email between the check and the insert
        raise ValueError("A user with this email already exists.")
    return user


def login_user(email, password):
    # Check the lock before the password, otherwise a locked-out attacker could
    # still learn when they've guessed right. Unknown emails are tracked too, so
    # the lockout response doesn't reveal which emails have accounts.
    check_not_locked(email)

    user = authenticate(email=email, password=password)
    if user is None:
        record_failed_login(email)
        raise InvalidCredentials()

    reset_failed_logins(email)
    if get_setting("REQUIRE_EMAIL_VERIFICATION") and not user.email_verified:
        raise EmailNotVerified()
    update_last_login(None, user)
    return user


# -----------------------------------------------------------------------------
# Email verification
# -----------------------------------------------------------------------------

def verify_email(uid, token):
    user = get_user_from_link(uid, token, email_verification_token)
    if user is None:
        raise InvalidLink()
    user.email_verified = True
    user.save(update_fields=["email_verified"])
    return user


def get_user_for_email(email, *, unverified=False):
    """The active user with this email, or None. For endpoints that must not reveal which exists."""
    users = CustomUser.objects.filter(email=CustomUser.objects.normalize_email(email), is_active=True)
    if unverified:
        users = users.filter(email_verified=False)
    return users.first()


# -----------------------------------------------------------------------------
# Passwords
# -----------------------------------------------------------------------------

def _set_new_password(user, password, field):
    # Run the host project's AUTH_PASSWORD_VALIDATORS against this user
    try:
        validate_password(password, user=user)
    except DjangoValidationError as e:
        raise serializers.ValidationError({field: list(e.messages)})
    user.set_password(password)
    user.save(update_fields=["password"])


def change_password(user, old_password, new_password):
    """Change the password and log out every session. Returns tokens for the current device."""
    if not user.check_password(old_password):
        raise serializers.ValidationError({"old_password": ["Incorrect password."]})
    _set_new_password(user, new_password, "new_password")
    # A password change is often a reaction to a suspected compromise, so end
    # every session, including any an attacker holds, and log this device back in
    revoke_all_sessions(user)
    send_password_changed_email(user)
    return get_tokens_for_user(user)


def reset_password(uid, token, new_password):
    user = get_user_from_link(uid, token, password_reset_token)
    if user is None or not user.is_active:
        raise InvalidLink()
    _set_new_password(user, new_password, "new_password")  # also invalidates the link
    revoke_all_sessions(user)
    # Clicking the emailed link proves they own the address, so they're verified,
    # and a lockout from someone guessing their old password no longer matters
    if not user.email_verified:
        user.email_verified = True
        user.save(update_fields=["email_verified"])
    unlock_account(user.email)
    send_password_changed_email(user)


# -----------------------------------------------------------------------------
# Account deactivation
# -----------------------------------------------------------------------------

def deactivate_account(user, password):
    # Ask for the password so a stolen access token alone can't close the account
    if not user.check_password(password):
        raise serializers.ValidationError({"password": ["Incorrect password."]})
    user.is_active = False
    user.save(update_fields=["is_active"])  # signals.py revokes every session


# -----------------------------------------------------------------------------
# Sessions
# -----------------------------------------------------------------------------
#
# Each logged-in device holds one refresh token. With ROTATE_REFRESH_TOKENS, every
# refresh swaps it for a new one and blacklists the old one, so a user's active
# sessions are their refresh tokens that are neither blacklisted nor expired.
# simplejwt already records every refresh token it issues in OutstandingToken.
#
# Revoking a session blacklists its refresh token. Access tokens already issued
# keep working until they expire, so keep ACCESS_TOKEN_LIFETIME short.
#
# The blacklist models are imported inside each function: importing them at the
# top would crash the whole package when token_blacklist isn't installed,
# instead of letting system check reusable_auth.E002 explain the problem.

def get_active_sessions(user):
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

    return (
        OutstandingToken.objects
        .filter(user=user, expires_at__gt=timezone.now(), blacklistedtoken__isnull=True)
        .order_by("-created_at")
    )


def revoke_session(user, session_id):
    """Revoke one of the user's sessions. Returns False if it isn't theirs or isn't active."""
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

    session = get_active_sessions(user).filter(id=session_id).first()
    if session is None:
        return False
    BlacklistedToken.objects.get_or_create(token=session)
    return True


def revoke_all_sessions(user):
    """Log the user out on every device. Returns how many sessions were revoked."""
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

    sessions = list(get_active_sessions(user))
    # ignore_conflicts: a concurrent request may have blacklisted one already
    BlacklistedToken.objects.bulk_create([BlacklistedToken(token=s) for s in sessions], ignore_conflicts=True)
    return len(sessions)


# -----------------------------------------------------------------------------
# Refresh token reuse detection
# -----------------------------------------------------------------------------
#
# With rotation, a refresh token is only ever used once: refreshing retires it
# and issues a new one. So if a retired token is presented again, two parties
# hold copies of it, and one of them stole it. We can't tell which one is the
# real user, so we revoke every session the user has. Both must log in again,
# and only the real user knows the password.
#
# Only tokens retired *by rotation* count. A token that was logged out or
# revoked is also blacklisted, but a device sending it again is normal (an app
# retrying after logout) and shouldn't log the user out everywhere. simplejwt
# doesn't record why a token was blacklisted, so we remember rotations
# ourselves, in the cache, until the token would have expired anyway. If the
# cache is cleared, detection is skipped for those tokens; they are still
# rejected as blacklisted.

def _rotated_key(jti):
    return f"reusable_auth:rotated_refresh:{jti}"


def _decode_refresh_token(raw_token):
    """Return the payload of a genuine, unexpired refresh token, or None."""
    if not isinstance(raw_token, str):
        return None
    try:
        # Verify the signature: never act on a token we didn't issue
        payload = token_backend.decode(raw_token, verify=True)
    except TokenBackendError:
        return None  # forged, malformed or expired
    if payload.get(jwt_settings.TOKEN_TYPE_CLAIM) != "refresh":
        return None
    return payload


def record_refresh_rotation(raw_token):
    """Called after a successful refresh: remember that this token was rotated."""
    payload = _decode_refresh_token(raw_token)
    if payload is None:
        return
    remaining = int(payload["exp"] - time.time())
    if remaining > 0:
        cache.set(_rotated_key(payload[jwt_settings.JTI_CLAIM]), time.time(), timeout=remaining)


def handle_refresh_token_reuse(raw_token):
    """
    Called when the refresh endpoint rejects a token. Returns True if it was a
    rotated refresh token being reused, and the user's sessions were revoked.
    """
    payload = _decode_refresh_token(raw_token)
    if payload is None:
        return False

    rotated_at = cache.get(_rotated_key(payload[jwt_settings.JTI_CLAIM]))
    if rotated_at is None:
        return False  # logged out, revoked, or never rotated: just reject it

    # Two browser tabs refreshing at the same moment both send the same token;
    # one wins and the other arrives just after. That's a race, not theft.
    if time.time() - rotated_at < get_setting("REFRESH_TOKEN_REUSE_GRACE"):
        return False

    user_id = payload.get(jwt_settings.USER_ID_CLAIM)
    user = CustomUser.objects.filter(**{jwt_settings.USER_ID_FIELD: user_id}).first()
    if user is None:
        return False

    revoked = revoke_all_sessions(user)
    logger.warning("Refresh token reuse detected: user_id=%s sessions_revoked=%d", user.pk, revoked)
    return True
