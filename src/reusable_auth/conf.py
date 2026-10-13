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
}


def get_setting(name):
    # Read at call time, not import time, so override_settings and runtime
    # changes take effect
    return getattr(settings, "REUSABLE_AUTH", {}).get(name, DEFAULTS[name])
