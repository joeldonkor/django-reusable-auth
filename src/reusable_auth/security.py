import hashlib
import logging
import time

from django.conf import settings
from django.core.cache import cache

from reusable_auth.managers import CustomUserManager

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Layer 2: failed-login tracking and account lockout (per email)
# -----------------------------------------------------------------------------
#
# IP throttling alone doesn't stop an attacker spreading guesses for one account
# across many IPs. This layer counts failures per email instead:
#
#   failures key: how many wrong passwords in the current window
#   lock key:     present while the account is locked; holds the unlock time
#   lockouts key: how many times the account was locked recently, used to make
#                 each new lock longer than the last (progressive lockout)
#
# All keys expire on their own, so nothing needs cleaning up.

DEFAULTS = {
    "LOGIN_MAX_FAILURES": 5,                 # wrong passwords allowed per window
    "LOGIN_FAILURE_WINDOW": 15 * 60,         # seconds the failure count is kept
    "LOGIN_LOCKOUT_DURATION": 15 * 60,       # seconds the first lock lasts; doubles on each repeat
    "LOGIN_LOCKOUT_MAX_DURATION": 24 * 60 * 60,  # longest a lock can get
    "LOGIN_LOCKOUT_RESET_AFTER": 24 * 60 * 60,   # seconds after a lock ends before doubling resets
}


class AccountLockedError(Exception):
    def __init__(self, retry_after):
        super().__init__("Too many failed login attempts. Try again later.")
        self.retry_after = retry_after


def get_setting(name):
    # Read at call time so the host project (and tests) can override it
    return getattr(settings, "REUSABLE_AUTH", {}).get(name, DEFAULTS[name])


def _digest(email):
    # Normalize so "Jane@x.com" and "jane@x.com" share one counter. Hash so the
    # address isn't stored or logged in plain text, and the key has a fixed, safe
    # length (memcached rejects long keys or ones with spaces).
    return hashlib.sha256(CustomUserManager.normalize_email(email).encode()).hexdigest()


def _keys(email):
    digest = _digest(email)
    return (
        f"reusable_auth:login_failures:{digest}",
        f"reusable_auth:login_lock:{digest}",
        f"reusable_auth:login_lockouts:{digest}",
    )


def check_not_locked(email):
    """Raise AccountLockedError if this email is currently locked out."""
    _, lock_key, _ = _keys(email)
    locked_until = cache.get(lock_key)
    if locked_until is not None:
        raise AccountLockedError(retry_after=max(1, int(locked_until - time.time())))


def record_failed_login(email):
    """Count a wrong password; lock the account once the limit is reached."""
    failures_key, lock_key, lockouts_key = _keys(email)
    window = get_setting("LOGIN_FAILURE_WINDOW")

    # add() only sets the key if it's missing, which starts the window on the first
    # failure. incr() is atomic on Redis/memcached, so parallel requests can't both
    # read 4 and write 5.
    cache.add(failures_key, 0, timeout=window)
    try:
        failures = cache.incr(failures_key)
    except ValueError:
        # The key expired between add() and incr()
        cache.set(failures_key, 1, timeout=window)
        failures = 1

    if failures < get_setting("LOGIN_MAX_FAILURES"):
        return

    # Progressive lockout: 15 min, 30 min, 1 h, ... up to the max. Without this an
    # attacker could keep making 5 guesses every 15 minutes indefinitely.
    lockouts = cache.get(lockouts_key, 0) + 1
    base = get_setting("LOGIN_LOCKOUT_DURATION")
    duration = min(base * 2 ** min(lockouts - 1, 32), get_setting("LOGIN_LOCKOUT_MAX_DURATION"))

    cache.set(lock_key, time.time() + duration, timeout=duration)
    cache.set(lockouts_key, lockouts, timeout=duration + get_setting("LOGIN_LOCKOUT_RESET_AFTER"))
    cache.delete(failures_key)  # start fresh once the lock expires

    logger.warning(
        "Account locked after %d failed logins: email_hash=%s lockout=%d duration=%ds",
        failures, _digest(email)[:12], lockouts, duration,
    )


def reset_failed_logins(email):
    """Call after a successful login: the real owner is back, so forget past failures."""
    failures_key, _, lockouts_key = _keys(email)
    cache.delete_many([failures_key, lockouts_key])


def unlock_account(email):
    """Remove any lock and failure history for this email. Returns True if it was locked."""
    failures_key, lock_key, lockouts_key = _keys(email)
    was_locked = cache.get(lock_key) is not None
    cache.delete_many([failures_key, lock_key, lockouts_key])
    if was_locked:
        logger.info("Account unlocked: email_hash=%s", _digest(email)[:12])
    return was_locked
