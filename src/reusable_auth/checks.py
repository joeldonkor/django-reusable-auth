from django.apps import apps
from django.conf import settings
from django.core.cache import caches
from django.core.cache.backends.dummy import DummyCache
from django.core.cache.backends.locmem import LocMemCache
from django.core.checks import Error, Tags, Warning, register

from reusable_auth.conf import DEFAULTS


# -----------------------------------------------------------------------------
# System checks
# -----------------------------------------------------------------------------
#
# Django runs these on runserver, migrate and `manage.py check`. A misconfigured
# cache doesn't raise any error; rate limiting just quietly stops working. These
# checks make that visible at startup instead of after an attack.

@register(Tags.security, Tags.caches)
def check_cache_backend(app_configs, **kwargs):
    cache = caches["default"]

    if isinstance(cache, DummyCache):
        return [Error(
            "The default cache is DummyCache, so rate limiting and account lockout are disabled.",
            hint="Configure a real cache in CACHES, such as RedisCache.",
            id="reusable_auth.E001",
        )]

    if isinstance(cache, LocMemCache) and not settings.DEBUG:
        return [Warning(
            "The default cache is LocMemCache. Each process keeps its own rate-limit "
            "counters, and they are lost on restart.",
            hint="Use a cache shared by all processes in production, such as RedisCache.",
            id="reusable_auth.W001",
        )]

    return []


@register()
def check_settings(app_configs, **kwargs):
    unknown = set(getattr(settings, "REUSABLE_AUTH", {})) - set(DEFAULTS)
    return [
        Warning(
            f"Unknown setting REUSABLE_AUTH[{name!r}] will be ignored.",
            hint=f"Valid settings: {', '.join(sorted(DEFAULTS))}.",
            id="reusable_auth.W002",
        )
        for name in sorted(unknown)
    ]


@register()
def check_token_blacklist_installed(app_configs, **kwargs):
    # Logout works by blacklisting the refresh token, which needs this app's tables
    if apps.is_installed("rest_framework_simplejwt.token_blacklist"):
        return []
    return [Error(
        "rest_framework_simplejwt.token_blacklist is not in INSTALLED_APPS, so logout cannot revoke tokens.",
        hint="Add it to INSTALLED_APPS and run migrate.",
        id="reusable_auth.E002",
    )]
