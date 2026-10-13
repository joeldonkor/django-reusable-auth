# django-reusable-auth

A secure, reusable authentication foundation for **Django and Django REST Framework (DRF)** projects.

## Overview

`django-reusable-auth` is an open-source authentication package designed to help Django developers implement authentication without repeatedly rebuilding the same authentication logic for every project.

The project provides a modular and configurable foundation for common authentication requirements such as user registration, login, JWT authentication, token management, password management, email verification, sessions, and security controls.

The goal is simple:

> **Build authentication once. Configure it for every project.**

## Why this project?

Authentication is a core part of almost every application, yet developers often find themselves implementing similar authentication functionality repeatedly.

This project aims to provide a reliable foundation that developers can install, configure, and extend according to the requirements of their application.

Instead of:

```text
Project A → Build authentication
Project B → Build authentication again
Project C → Build authentication again
```

The goal is:

```text
                 django-reusable-auth
                         │
          ┌──────────────┼──────────────┐
          ↓              ↓              ↓
       Project A      Project B      Project C
```

## Core Goals

* 🔐 **Security-first** — secure defaults and established Django security practices.
* ♻️ **Reusable** — designed to work across multiple Django/DRF projects.
* ⚙️ **Configurable** — adapt authentication behavior without modifying the package source.
* 🧩 **Modular** — authentication components should be independently maintainable and extensible.
* 🧪 **Tested** — authentication and security flows will be covered by automated tests.
* 📚 **Well documented** — developers should be able to install and use the package without needing to understand its internal implementation.
* 🌱 **Open source** — developed transparently and intended for community use and contribution.

## Planned Features

The project will be developed incrementally.

### Authentication

* User registration
* Login
* Logout ✅
* JWT access and refresh tokens
* Token refresh
* Token revocation ✅
* Current-user endpoint ✅

### Account Management

* Password change ✅
* Password reset ✅
* Email verification ✅
* Email verification resend ✅
* Account activation/deactivation ✅
* Session management ✅

### Security

* Secure password hashing
* Password validation
* Refresh-token rotation
* Token expiration
* Token reuse detection ✅
* Session revocation ✅
* Brute-force protection (progressive account lockout) ✅
* Rate limiting (per-IP, per-endpoint throttling) ✅
* Security-focused automated tests

### Developer Experience

* Configurable settings
* REST API endpoints
* OpenAPI documentation
* Example Django project
* Automated testing
* CI/CD
* PyPI distribution

## Technology

The initial version is planned around:

* **Python 3.14**
* **Django**
* **Django REST Framework**
* **PostgreSQL**
* **JWT**
* **pytest / pytest-django**
* **GitHub Actions**

## Development Philosophy

This project will prioritize **security, simplicity, maintainability, and extensibility** over adding as many features as possible.

The package will rely on established Django and Python security mechanisms rather than implementing custom cryptographic algorithms or security primitives.

The initial release will focus on providing a strong authentication foundation before expanding into advanced capabilities such as social authentication, two-factor authentication, passkeys, and more advanced authorization.

## Project Status

🚧 **Early Development**

The project is currently being designed and developed. APIs, configuration options, and internal architecture may change before the first stable release.

## Roadmap

### v0.x

Build and validate the core authentication foundation:

* Custom user model
* Registration
* Login
* JWT authentication
* Logout
* Password management
* Email verification
* Session management
* Token security
* Security testing
* Documentation

### v1.0

The first stable release will aim to provide:

* Production-oriented authentication flows
* Secure defaults
* Comprehensive automated tests
* Configurable authentication behavior
* Complete API documentation
* Example project
* PyPI package
* Security documentation

### Future

Potential future capabilities include:

* Social authentication
* Two-factor authentication
* Advanced role-based access control
* Passkeys/WebAuthn
* Additional authentication providers
* Potential standalone authentication services

## Project Structure

The project is intended to separate reusable authentication functionality from the application that consumes it.

```text
django-reusable-auth/
│
├── reusable_auth/       # Authentication package
├── tests/               # Unit, API and security tests
├── examples/            # Example Django projects
├── docs/                # Documentation
├── pyproject.toml
├── README.md
├── SECURITY.md
├── CONTRIBUTING.md
├── CHANGELOG.md
└── LICENSE
```

## API

| Method | Endpoint | Auth | Body | Success |
|---|---|---|---|---|
| `POST` | `/auth/register/` | — | `first_name`, `last_name`, `email`, `password` | `201` `{"detail": ...}` |
| `POST` | `/auth/login/` | — | `email`, `password` | `200` `{"access": ..., "refresh": ...}` |
| `POST` | `/auth/refresh/` | — | `refresh` | `200` `{"access": ..., "refresh": ...}` |
| `POST` | `/auth/logout/` | — | `refresh` | `200` `{"detail": "Logged out."}` |
| `GET` | `/auth/me/` | `Bearer <access>` | — | `200` user object |
| `GET` | `/auth/sessions/` | `Bearer <access>` | — | `200` list of active sessions |
| `DELETE` | `/auth/sessions/` | `Bearer <access>` | — | `204` (log out everywhere) |
| `DELETE` | `/auth/sessions/<id>/` | `Bearer <access>` | — | `204` (`404` if not yours or not active) |
| `POST` | `/auth/me/deactivate/` | `Bearer <access>` | `password` | `204` |
| `POST` | `/auth/email/verify/` | — | `uid`, `token` | `200` `{"detail": ...}` |
| `POST` | `/auth/email/verify/resend/` | — | `email` | `200` `{"detail": ...}` |
| `POST` | `/auth/password/change/` | `Bearer <access>` | `old_password`, `new_password` | `200` `{"access": ..., "refresh": ...}` |
| `POST` | `/auth/password/reset/` | — | `email` | `200` `{"detail": ...}` |
| `POST` | `/auth/password/reset/confirm/` | — | `uid`, `token`, `new_password` | `200` `{"detail": ...}` |

Registration, verification resend and password reset respond the same way whether or not the email has an account, so they can't be used to discover which emails are registered. When someone registers with an email that already has an account, the owner gets an email about it instead.

Logout blacklists the refresh token. It doesn't need an access token, since that has often expired by the time a user logs out. Access tokens can't be revoked and stay valid until they expire, so keep `ACCESS_TOKEN_LIFETIME` short.

### Sessions

Each logged-in device holds one refresh token, which is one session:

```json
[{"id": 42, "issued_at": "2026-10-13T15:28:00Z", "expires_at": "2026-10-20T15:28:00Z"}]
```

`issued_at` is when that device last logged in or refreshed. A session's `id` changes each time it refreshes, because rotation issues a new token. Revoking a session stops it from refreshing; its current access token keeps working until it expires.

### Refresh token reuse detection

With rotation on, a refresh token can only be used once. If a token that was already rotated is used again, two parties have a copy of it and one of them stole it. The package then **revokes every session for that user**, so both must log in again, and only the real owner knows the password.

* Tokens that were logged out or revoked are just rejected. A device retrying with one doesn't log the user out everywhere.
* Resending a token within `REFRESH_TOKEN_REUSE_GRACE` seconds (default `10`) of its rotation is treated as two tabs refreshing at once, not theft.
* Rotations are tracked in the cache, so this needs the shared cache described under [Rate Limiting](#rate-limiting).

Requires rotation in your simplejwt settings (the package reports `reusable_auth.W003` if it's off):

```python
SIMPLE_JWT = {
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}
```

### Email verification

New users must verify their email before they can log in (`REQUIRE_EMAIL_VERIFICATION`, on by default). Registration sends a link; until it's used, login with the correct password returns `403` with code `email_not_verified`, so your frontend can offer to resend it.

Superusers created with `createsuperuser` are verified automatically. Users who existed before this feature was added are marked verified by the migration.

### Passwords

* **Change** (logged in): requires the current password, logs out **every** session, and returns fresh tokens for the current device. The user gets a "your password was changed" email.
* **Reset** (forgotten): `/auth/password/reset/` emails a link; `/auth/password/reset/confirm/` sets the new password. This logs out every session, marks the email verified (the user just proved they own it) and clears any login lockout.

Emailed links work once and expire after Django's `PASSWORD_RESET_TIMEOUT` (3 days by default). They're signed with `SECRET_KEY` and nothing is stored in the database.

### Account deactivation

`/auth/me/deactivate/` requires the user's password, so a stolen access token alone can't close the account. It sets `is_active = False` and revokes every session. Deactivating a user anywhere else, such as the Django admin, also revokes their sessions, so reactivating the account later doesn't bring old sessions back. Reactivation is done by an admin.

### Errors

Every endpoint uses Django REST Framework's standard error format:

| Status | Body | When |
|---|---|---|
| `400` | `{"email": ["Enter a valid email address."], ...}` | Invalid input, keyed by field |
| `400` | `{"detail": "This link is invalid or has expired."}` | Bad or used emailed link |
| `401` | `{"detail": "Invalid email or password."}` | Wrong credentials, or a missing/invalid token |
| `403` | `{"detail": "Verify your email address before logging in."}` | Correct password, email not verified |
| `429` | `{"detail": "..."}` + `Retry-After` header | Rate limited or account locked |

The package doesn't set a custom `EXCEPTION_HANDLER`, so it never changes how the rest of your API reports errors.

### Requirements

Logout needs simplejwt's blacklist app (the package reports `reusable_auth.E002` at startup if it's missing):

```python
INSTALLED_APPS = [
    # ...
    "rest_framework_simplejwt.token_blacklist",
]
```

### Email setup

Verification, password reset and security notices are sent by email, so configure:

1. **An email backend.** Django's `EMAIL_*` settings, or `MAILERS` on Django 6.1+.
2. **Template loading**, so the package's email templates can be found (`reusable_auth.E003` if not):

   ```python
   TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True}]
   ```

3. **Links to your frontend** (`reusable_auth.W004` if not set). The package fills in `{uid}` and `{token}`; your page should POST them to the matching confirm endpoint:

   ```python
   REUSABLE_AUTH = {
       "EMAIL_VERIFICATION_URL": "https://app.example.com/verify-email?uid={uid}&token={token}",
       "PASSWORD_RESET_URL": "https://app.example.com/reset-password?uid={uid}&token={token}",
   }
   ```

**Changing the emails:** each email is rendered from `reusable_auth/email/<kind>_subject.txt` and `<kind>_body.txt`, plus `<kind>_body.html` if present. The kinds are `verify_email`, `password_reset`, `password_changed` and `account_exists`. To change one, put a file at the same path in your project's `templates/` folder.

**Sending them your own way:** set `REUSABLE_AUTH["EMAIL_SENDER"]` to the dotted path of a function `send(kind, user, context)`. This is **recommended in production**: queue the email (for example with Celery) instead of sending it during the request. Sending takes time, and a reset request for a real account is otherwise measurably slower than one for an unknown email, which leaks which emails are registered.

A failure to send is logged on the `reusable_auth.emails` logger and never turned into an error response, for the same reason. The same kind of email is sent to the same address at most once per `EMAIL_COOLDOWN` seconds (default 60), so nobody can flood an inbox from many IPs.

The views set their own authentication and permission classes, so they work regardless of your `REST_FRAMEWORK` defaults. For example, login still works if your project sets `DEFAULT_PERMISSION_CLASSES` to `IsAuthenticated`.

## Rate Limiting

The auth endpoints are protected by two layers that work out of the box:

* **Request throttling (per IP)** — limits how often one IP address can call each endpoint.
* **Account lockout (per email)** — temporarily locks an email after repeated wrong passwords, even if the attempts come from many IPs.

Both return **`429 Too Many Requests`** with a `Retry-After` header.

### ⚠️ Production: configure a shared cache

Throttle counters and lockouts are stored in **Django's cache**. If you don't configure one, Django uses `LocMemCache`, which is **not suitable for production**:

* Each server process keeps its own counters, so with 4 workers an attacker gets 4× the attempts.
* Counters and lockouts are lost whenever the server restarts.

Use a cache that all processes share, such as Redis:

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379",
    }
}
```

### ⚠️ Behind a proxy or load balancer

If your app runs behind Nginx, a load balancer, or a platform like Heroku, every request may appear to come from the proxy's IP, so all users would share one limit. Tell DRF how many proxies sit in front of your app so it reads the real client IP from `X-Forwarded-For`:

```python
REST_FRAMEWORK = {
    "NUM_PROXIES": 1,
}
```

### Configuration

The defaults can be overridden in your settings:

```python
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_RATES": {
        "auth_login": "10/min",      # default
        "auth_register": "10/hour",  # default
        "auth_refresh": "30/min",    # default
        "auth_logout": "30/min",     # default
        "auth_password_reset": "5/hour",       # default
        "auth_verification_resend": "5/hour",  # default
        "auth_link_confirm": "30/hour",        # default: verify email, confirm reset
        "auth_account_change": "10/hour",      # default: password change, deactivation
        # set any scope to None to disable it
    },
}

REUSABLE_AUTH = {
    "LOGIN_MAX_FAILURES": 5,             # wrong passwords before an account is locked
    "LOGIN_FAILURE_WINDOW": 900,         # seconds failed attempts are remembered
    "LOGIN_LOCKOUT_DURATION": 900,       # seconds the first lock lasts
    "LOGIN_LOCKOUT_MAX_DURATION": 86400, # cap for repeated locks
    "LOGIN_LOCKOUT_RESET_AFTER": 86400,  # quiet seconds after a lock before durations reset
    "REFRESH_TOKEN_REUSE_GRACE": 10,     # see "Refresh token reuse detection"
    "REQUIRE_EMAIL_VERIFICATION": True,  # see "Email verification"
    "EMAIL_VERIFICATION_URL": None,      # see "Email setup"
    "PASSWORD_RESET_URL": None,          # see "Email setup"
    "EMAIL_COOLDOWN": 60,                # seconds between emails of one kind to one address
    "EMAIL_SENDER": "reusable_auth.emails.send_templated_email",
}
```

**Progressive lockout:** each time the same account is locked again, the lock lasts twice as long (15 min → 30 min → 1 h → …, up to `LOGIN_LOCKOUT_MAX_DURATION`). A successful login, or `LOGIN_LOCKOUT_RESET_AFTER` seconds without a new lock, resets it. To use a fixed duration instead, set `LOGIN_LOCKOUT_MAX_DURATION` equal to `LOGIN_LOCKOUT_DURATION`.

### Unlocking an account

If a real user locks themselves out, clear the lock without waiting:

```bash
python manage.py unlock_account jane@example.com
```

or from code: `from reusable_auth.security import unlock_account`.

### Startup checks and logging

The package adds Django system checks that run on `runserver`, `migrate` and `manage.py check`:

| ID | Level | Meaning |
|---|---|---|
| `reusable_auth.E001` | Error | The cache is `DummyCache`, so rate limiting is **completely disabled** |
| `reusable_auth.E002` | Error | `token_blacklist` isn't installed, so logout can't revoke tokens |
| `reusable_auth.E003` | Error | Email templates can't be loaded (no `TEMPLATES` with `APP_DIRS`) |
| `reusable_auth.W004` | Warning | `EMAIL_VERIFICATION_URL` or `PASSWORD_RESET_URL` isn't set |
| `reusable_auth.W003` | Warning | Refresh token rotation is off, so reuse detection is disabled |
| `reusable_auth.W001` | Warning | The cache is `LocMemCache` while `DEBUG=False` |
| `reusable_auth.W002` | Warning | Unknown key in `REUSABLE_AUTH` (likely a typo) |

Lockouts are logged as warnings on the `reusable_auth.security` logger. Emails are logged as a short hash, never in plain text.

> **Note:** account lockout can be triggered by anyone who knows a user's email. Lockouts expire automatically to limit the impact, and IP throttling limits how quickly one client can cause them.

## Security

Security is a core requirement of this project.

If you discover a security vulnerability, please do **not** disclose it publicly through a GitHub issue. A dedicated security reporting process will be documented before the first stable release.

> This project does not claim to make applications completely secure. Authentication security depends on correct configuration, deployment practices, dependencies, and the application using the package.

## License

This project will be released under the **MIT License**.

---

**django-reusable-auth**

> Build authentication once. Configure it for every project.
