from django.apps import apps
from django.conf import settings
from django.core.cache import caches
from django.core.cache.backends.dummy import DummyCache
from django.core.cache.backends.locmem import LocMemCache
from django.core.checks import Error, Tags, Warning, register
from django.template import TemplateDoesNotExist
from django.template.loader import get_template

from reusable_auth.conf import DEFAULTS, get_setting


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


@register()
def check_refresh_token_rotation(app_configs, **kwargs):
    from rest_framework_simplejwt.settings import api_settings as jwt_settings

    # Without rotation + blacklisting, a used refresh token stays valid, so a
    # stolen one can be replayed until it expires and reuse can't be detected
    if jwt_settings.ROTATE_REFRESH_TOKENS and jwt_settings.BLACKLIST_AFTER_ROTATION:
        return []
    return [Warning(
        "Refresh token rotation is off, so refresh token reuse detection is disabled.",
        hint='Set "ROTATE_REFRESH_TOKENS": True and "BLACKLIST_AFTER_ROTATION": True in SIMPLE_JWT.',
        id="reusable_auth.W003",
    )]


@register()
def check_email_templates(app_configs, **kwargs):
    # Only the default sender uses the templates
    if get_setting("EMAIL_SENDER") != DEFAULTS["EMAIL_SENDER"]:
        return []
    try:
        get_template("reusable_auth/email/verify_email_body.txt")
    except TemplateDoesNotExist:
        return [Error(
            "The reusable_auth email templates can't be found, so verification and reset emails can't be sent.",
            hint='Add a Django template engine to TEMPLATES with "APP_DIRS": True.',
            id="reusable_auth.E003",
        )]
    return []


@register()
def check_email_link_urls(app_configs, **kwargs):
    needed = ["PASSWORD_RESET_URL"]
    if get_setting("REQUIRE_EMAIL_VERIFICATION"):
        needed.append("EMAIL_VERIFICATION_URL")
    return [
        Warning(
            f"REUSABLE_AUTH[{name!r}] is not set, so emails will contain a raw uid and token instead of a link.",
            hint='Set it to your frontend page, e.g. "https://app.example.com/page?uid={uid}&token={token}".',
            id="reusable_auth.W004",
        )
        for name in needed
        if not get_setting(name)
    ]
