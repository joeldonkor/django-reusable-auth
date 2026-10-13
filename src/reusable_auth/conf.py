from django.conf import settings


# -----------------------------------------------------------------------------
# Package settings
# -----------------------------------------------------------------------------
#
# Host projects override any of these in their settings:
#
#     REUSABLE_AUTH = {"LOGIN_MAX_FAILURES": 10}
#
# Every setting needs a default here; the system checks use this dict to warn
# about unknown (usually misspelled) keys.

DEFAULTS = {
    # Account lockout (see security.py)
    "LOGIN_MAX_FAILURES": 5,                     # wrong passwords allowed per window
    "LOGIN_FAILURE_WINDOW": 15 * 60,             # seconds the failure count is kept
    "LOGIN_LOCKOUT_DURATION": 15 * 60,           # seconds the first lock lasts; doubles on each repeat
    "LOGIN_LOCKOUT_MAX_DURATION": 24 * 60 * 60,  # longest a lock can get
    "LOGIN_LOCKOUT_RESET_AFTER": 24 * 60 * 60,   # seconds after a lock ends before doubling resets

    # Refresh token reuse detection (see services.py)
    "REFRESH_TOKEN_REUSE_GRACE": 10,  # seconds a just-rotated token may be resent without revoking sessions

    # Email verification and password reset (see emails.py)
    "REQUIRE_EMAIL_VERIFICATION": True,  # block login until the user clicks the emailed link
    # Frontend pages the emailed links point to. {uid} and {token} are filled in;
    # the page should POST them to the matching confirm endpoint.
    "EMAIL_VERIFICATION_URL": None,  # e.g. "https://app.example.com/verify-email?uid={uid}&token={token}"
    "PASSWORD_RESET_URL": None,      # e.g. "https://app.example.com/reset-password?uid={uid}&token={token}"
    "EMAIL_COOLDOWN": 60,            # seconds before the same kind of email is sent to the same address again
    "EMAIL_SENDER": "reusable_auth.emails.send_templated_email",  # dotted path; replace to use your own
}


def get_setting(name):
    # Read at call time, not import time, so override_settings and runtime
    # changes take effect
    return getattr(settings, "REUSABLE_AUTH", {}).get(name, DEFAULTS[name])
