"""
Settings for the django-reusable-auth demo project.

Only for trying the package locally: DEBUG is on, the secret key is public and
emails are printed to the console. Every setting the package needs is marked
with "reusable_auth".
"""
from datetime import timedelta
from pathlib import Path

import django

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "demo-only-this-key-is-public-never-use-it-in-production"
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",  # reusable_auth: logout and sessions
    "drf_spectacular",                           # optional: API docs at /api/docs/
    "reusable_auth",
]

# reusable_auth: must be set before the first migrate of a new project
AUTH_USER_MODEL = "reusable_auth.CustomUser"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "demo.urls"

# reusable_auth: APP_DIRS lets Django find the package's email templates
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
STATIC_URL = "static/"

# reusable_auth: emails are printed in the runserver terminal, so you can copy
# the verification and reset links. Django 6.1 replaced EMAIL_BACKEND with
# MAILERS and refuses to start if both are set.
if django.VERSION >= (6, 1):
    MAILERS = {"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# reusable_auth: rate limits and lockouts live in the cache. The default
# in-memory cache is fine here; production needs a shared one such as Redis.

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,     # reusable_auth: needed for reuse detection
    "BLACKLIST_AFTER_ROTATION": True,  # reusable_auth: needed for reuse detection
}

REUSABLE_AUTH = {
    # Where the emailed links point. A real project would use its frontend's
    # pages; there is no frontend here, so copy uid and token from the link
    # into the confirm endpoints in the API docs.
    "EMAIL_VERIFICATION_URL": "http://localhost:3000/verify-email?uid={uid}&token={token}",
    "PASSWORD_RESET_URL": "http://localhost:3000/reset-password?uid={uid}&token={token}",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "django-reusable-auth demo",
}
