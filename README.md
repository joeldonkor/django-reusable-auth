# django-reusable-auth

[![tests](https://github.com/joeldonkor/django-reusable-auth/actions/workflows/tests.yaml/badge.svg)](https://github.com/joeldonkor/django-reusable-auth/actions/workflows/tests.yaml)
[![PyPI](https://img.shields.io/pypi/v/django-reusable-auth)](https://pypi.org/project/django-reusable-auth/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/joeldonkor/django-reusable-auth/blob/main/LICENSE)

Build authentication once. Configure it for every project.

django-reusable-auth is a JWT authentication API for Django REST Framework. It
handles the parts most projects end up rebuilding: registration, login, email
verification, password reset, sessions, and protection against brute-force
attacks. It is built on [Simple JWT](https://github.com/jazzband/djangorestframework-simplejwt)
and Django's own security primitives, with no custom cryptography.

Features:

- Email-based user model, with case-insensitive emails
- Registration, login, logout and token refresh
- Email verification and password reset through single-use emailed links
- Password change, account deactivation and session management
- Refresh token rotation with reuse detection
- Per-IP rate limiting and progressive account lockout
- Responses that don't reveal which emails are registered
- Startup checks that flag insecure configuration
- Optional OpenAPI schema through drf-spectacular

Tested on Python 3.10–3.14 and Django 5.2–6.1, against SQLite, PostgreSQL and
Redis.

## Installation

```bash
pip install django-reusable-auth
```

Requires Django 5.2+, Django REST Framework 3.16+ and Simple JWT 5.5+, which are
installed with it. For the OpenAPI schema, install
`django-reusable-auth[openapi]` instead.

## Quick start

The package provides its own user model. Django can't easily change the user
model of a project that has already been migrated, so add the package before
your first `migrate`.

Add to your settings:

```python
from datetime import timedelta

INSTALLED_APPS = [
    # ...
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "reusable_auth",
]

AUTH_USER_MODEL = "reusable_auth.CustomUser"

# APP_DIRS lets Django find the package's email templates
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "APP_DIRS": True,
    # ...
}]

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

REUSABLE_AUTH = {
    # Pages in your frontend that the emailed links open
    "EMAIL_VERIFICATION_URL": "https://app.example.com/verify-email?uid={uid}&token={token}",
    "PASSWORD_RESET_URL": "https://app.example.com/reset-password?uid={uid}&token={token}",
}
```

You also need an email backend (`EMAIL_BACKEND`, or `MAILERS` on Django 6.1+).

Include the URLs:

```python
urlpatterns = [
    path("api/", include("reusable_auth.urls")),
]
```

Then migrate, and run Django's checks. The package reports any missing setup:

```bash
python manage.py migrate
python manage.py check
```

Before deploying, read [Production](#production).

The [demo project](https://github.com/joeldonkor/django-reusable-auth/tree/main/examples/demo)
is a complete working setup with Swagger UI.

## Endpoints

Paths are relative to where you include the URLs (`/api/` above).

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| POST | `auth/register/` | | `first_name`, `last_name`, `email`, `password` | 201 |
| POST | `auth/login/` | | `email`, `password` | 200 `access`, `refresh` |
| POST | `auth/refresh/` | | `refresh` | 200 `access`, `refresh` |
| POST | `auth/logout/` | | `refresh` | 200 |
| GET | `auth/me/` | Bearer | | 200 user |
| POST | `auth/me/deactivate/` | Bearer | `password` | 204 |
| GET | `auth/sessions/` | Bearer | | 200 list of sessions |
| DELETE | `auth/sessions/` | Bearer | | 204 |
| DELETE | `auth/sessions/<id>/` | Bearer | | 204 |
| POST | `auth/email/verify/` | | `uid`, `token` | 200 |
| POST | `auth/email/verify/resend/` | | `email` | 200 |
| POST | `auth/password/change/` | Bearer | `old_password`, `new_password` | 200 `access`, `refresh` |
| POST | `auth/password/reset/` | | `email` | 200 |
| POST | `auth/password/reset/confirm/` | | `uid`, `token`, `new_password` | 200 |

Other 200 and 201 responses contain a `detail` message. With drf-spectacular
installed, the full schema is generated for these endpoints.

### Errors

All errors use Django REST Framework's standard format:

| Status | Body | Cause |
|---|---|---|
| 400 | `{"email": ["Enter a valid email address."]}` | Invalid input, keyed by field |
| 400 | `{"detail": "This link is invalid or has expired."}` | Bad or already used emailed link |
| 401 | `{"detail": "Invalid email or password."}` | Wrong credentials, or a missing or invalid token |
| 403 | `{"detail": "Verify your email address before logging in."}` | Correct password, but email not verified |
| 429 | `{"detail": "..."}` | Rate limited or account locked; see the `Retry-After` header |

The package doesn't set `EXCEPTION_HANDLER`, so the rest of your API is
unaffected.

## How it works

### Registration and email verification

Registration sends a verification link, and login returns 403 (code
`email_not_verified`) until the user opens it. Set `REQUIRE_EMAIL_VERIFICATION`
to `False` to allow login without verifying.

If someone registers with an email that already has an account, the response is
the same as for a new signup, and the account owner is notified by email
instead. Verification resend and password reset also respond identically for
every email, so none of these endpoints reveal which emails are registered.

Users created with `createsuperuser` are verified automatically.

### Emailed links

Verification and reset links carry a `uid` and a `token`. Your frontend page
reads them from the URL and POSTs them to the matching confirm endpoint.

Tokens are signed with `SECRET_KEY` and nothing is stored in the database. A
link stops working once it has been used, and expires after Django's
`PASSWORD_RESET_TIMEOUT` (3 days by default).

### Sessions and logout

Each logged-in device holds one refresh token, which is listed as a session.
Logout, revoking a session, changing or resetting the password, and
deactivating the account all revoke refresh tokens. Access tokens already
issued stay valid until they expire, so keep `ACCESS_TOKEN_LIFETIME` short.

Logout only needs the refresh token, since the access token has often expired
by then.

Session IDs change on every refresh, because rotation issues a new token.

### Refresh token reuse detection

With rotation enabled, each refresh token can be used only once. If an
already-rotated token is used again, someone has a copy of it, so every session
of that user is revoked and both parties have to log in again.

Two requests sending the same token within `REFRESH_TOKEN_REUSE_GRACE` seconds
(10 by default), such as two browser tabs refreshing at once, are not treated as
reuse. Tokens that were logged out or revoked are simply rejected.

### Passwords and deactivation

Changing the password requires the current one. It logs out every session and
returns new tokens for the current device. Resetting it also logs out every
session, and marks the email as verified and clears any lockout, since the user
has just proved they own the address. Both send a notification email.

Deactivation requires the password and revokes every session. Deactivating a
user elsewhere, for example in the Django admin, revokes their sessions too, so
reactivating the account doesn't restore them.

### Rate limiting and account lockout

The public endpoints, password change and deactivation are rate-limited per IP
address. Separately, an account is locked
after 5 failed logins within 15 minutes, however many IPs they come from. The lock lasts 15
minutes and doubles each time it recurs, up to 24 hours. Both return 429 with a
`Retry-After` header.

Anyone who knows an email can trigger its lockout. Locks expire on their own,
and an administrator can clear one early:

```bash
python manage.py unlock_account jane@example.com
```

## Configuration

### Package settings

Set any of these in a `REUSABLE_AUTH` dict in your settings:

| Setting | Default | Description |
|---|---|---|
| `REQUIRE_EMAIL_VERIFICATION` | `True` | Block login until the email is verified |
| `EMAIL_VERIFICATION_URL` | `None` | Frontend URL for verification links, with `{uid}` and `{token}` |
| `PASSWORD_RESET_URL` | `None` | Frontend URL for reset links, with `{uid}` and `{token}` |
| `EMAIL_SENDER` | built-in | Dotted path to a function that sends the emails |
| `EMAIL_COOLDOWN` | `60` | Seconds before the same email can be sent to the same address again |
| `LOGIN_MAX_FAILURES` | `5` | Failed logins before an account is locked |
| `LOGIN_FAILURE_WINDOW` | `900` | Seconds failed logins are counted over |
| `LOGIN_LOCKOUT_DURATION` | `900` | Seconds the first lock lasts |
| `LOGIN_LOCKOUT_MAX_DURATION` | `86400` | Longest lock, after repeated doubling |
| `LOGIN_LOCKOUT_RESET_AFTER` | `86400` | Seconds without a lock before durations return to the first one |
| `REFRESH_TOKEN_REUSE_GRACE` | `10` | Seconds a just-rotated token can be resent without counting as reuse |

### Rate limits

Override them in `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`, or set a scope to
`None` to disable it:

| Scope | Default | Endpoints |
|---|---|---|
| `auth_login` | `10/min` | Login |
| `auth_register` | `10/hour` | Register |
| `auth_refresh` | `30/min` | Refresh |
| `auth_logout` | `30/min` | Logout |
| `auth_password_reset` | `5/hour` | Request a password reset |
| `auth_verification_resend` | `5/hour` | Resend verification |
| `auth_link_confirm` | `30/hour` | Verify email, confirm password reset |
| `auth_account_change` | `10/hour` | Change password, deactivate |

### Emails

The package sends four emails: `verify_email`, `password_reset`,
`password_changed` and `account_exists`. Each is rendered from
`reusable_auth/email/<name>_subject.txt` and `<name>_body.txt`, plus
`<name>_body.html` if it exists. To change the wording, add a template at the
same path in your project.

To send emails another way, such as through a task queue, set `EMAIL_SENDER`
to a function accepting `kind`, `user` and `context` keyword arguments.

Sending failures are logged to the `reusable_auth.emails` logger rather than
returned as errors, so that a failed send doesn't reveal that an account exists.

## Production

- **Use a shared cache**, such as Redis. Rate limits, lockouts and reuse
  detection are stored in Django's cache. The default `LocMemCache` is separate
  for each process and cleared on restart, which weakens all three.

  ```python
  CACHES = {
      "default": {
          "BACKEND": "django.core.cache.backends.redis.RedisCache",
          "LOCATION": "redis://127.0.0.1:6379",
      }
  }
  ```

- **Set `NUM_PROXIES`** in `REST_FRAMEWORK` if the app runs behind a proxy or
  load balancer. Otherwise every client appears to have the proxy's IP and
  shares one rate limit. Setting it too high lets clients spoof their IP.
- **Keep `SECRET_KEY` secret.** It signs every token and emailed link; anyone
  who has it can log in as any user.
- **Send emails in the background**, through `EMAIL_SENDER`. Sending during the
  request makes password reset measurably slower for registered emails than
  for unknown ones.
- **Keep `ACCESS_TOKEN_LIFETIME` short**, since access tokens can't be revoked.

### System checks

The package registers checks that run with `migrate`, `runserver` and
`manage.py check`:

| ID | Problem |
|---|---|
| `reusable_auth.E001` | The cache is `DummyCache`, so rate limiting is disabled |
| `reusable_auth.E002` | `rest_framework_simplejwt.token_blacklist` isn't installed |
| `reusable_auth.E003` | The email templates can't be loaded |
| `reusable_auth.W001` | The cache is `LocMemCache` while `DEBUG` is off |
| `reusable_auth.W002` | `REUSABLE_AUTH` contains an unknown setting |
| `reusable_auth.W003` | Refresh token rotation is off, so reuse detection is disabled |
| `reusable_auth.W004` | `EMAIL_VERIFICATION_URL` or `PASSWORD_RESET_URL` isn't set |

Lockouts are logged to the `reusable_auth.security` logger, with emails hashed.

## Roadmap

Social login, two-factor authentication and passkeys are not part of 1.x but
may be added later.

## Contributing

Contributions are welcome. See
[CONTRIBUTING.md](https://github.com/joeldonkor/django-reusable-auth/blob/main/CONTRIBUTING.md)
for the development setup, and the
[changelog](https://github.com/joeldonkor/django-reusable-auth/blob/main/CHANGELOG.md)
for release notes.

Please report security issues privately, as described in
[SECURITY.md](https://github.com/joeldonkor/django-reusable-auth/blob/main/SECURITY.md),
rather than in a public issue.

## License

[MIT](https://github.com/joeldonkor/django-reusable-auth/blob/main/LICENSE)
