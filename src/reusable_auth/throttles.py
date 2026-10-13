from rest_framework.settings import api_settings
from rest_framework.throttling import SimpleRateThrottle


# -----------------------------------------------------------------------------
# Layer 1: request throttling (per IP, per endpoint)
# -----------------------------------------------------------------------------

class AuthRateThrottle(SimpleRateThrottle):
    """
    Limits how often one IP address can hit a single auth endpoint.

    Each subclass sets a `scope` (which endpoint) and a `default_rate`. The host
    project can override a rate, or switch it off with None, in settings:

        REST_FRAMEWORK = {"DEFAULT_THROTTLE_RATES": {"auth_login": "20/min"}}

    Counters live in Django's cache, so production needs a cache shared by all
    workers (e.g. Redis). The default LocMemCache is per process.
    """
    default_rate = None

    def get_rate(self):
        # DRF raises ImproperlyConfigured when a scope has no rate; falling back to
        # default_rate means the package works without any settings. api_settings is
        # read on each call (not cached on the class) so setting changes apply.
        return api_settings.DEFAULT_THROTTLE_RATES.get(self.scope, self.default_rate)

    def get_cache_key(self, request, view):
        # get_ident() is the client IP. Behind a proxy, set NUM_PROXIES in
        # REST_FRAMEWORK so DRF reads X-Forwarded-For instead of the proxy's IP.
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


# Every public auth endpoint gets its own scope, so one endpoint being hammered
# doesn't use up another's budget. New endpoints (password reset, email
# verification resend, ...) should add a subclass here before they ship.

class LoginRateThrottle(AuthRateThrottle):
    scope = "auth_login"
    default_rate = "10/min"


class RegisterRateThrottle(AuthRateThrottle):
    scope = "auth_register"
    default_rate = "10/hour"


class RefreshRateThrottle(AuthRateThrottle):
    scope = "auth_refresh"
    default_rate = "30/min"
