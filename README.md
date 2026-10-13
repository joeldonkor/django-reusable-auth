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
* Logout
* JWT access and refresh tokens
* Token refresh
* Token revocation
* Current-user endpoint

### Account Management

* Password change
* Password reset
* Email verification
* Email verification resend
* Account activation/deactivation
* Session management

### Security

* Secure password hashing
* Password validation
* Refresh-token rotation
* Token expiration
* Token reuse detection
* Session revocation
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
        "auth_refresh": "30/min",    # default; set any scope to None to disable it
    },
}

REUSABLE_AUTH = {
    "LOGIN_MAX_FAILURES": 5,             # wrong passwords before an account is locked
    "LOGIN_FAILURE_WINDOW": 900,         # seconds failed attempts are remembered
    "LOGIN_LOCKOUT_DURATION": 900,       # seconds the first lock lasts
    "LOGIN_LOCKOUT_MAX_DURATION": 86400, # cap for repeated locks
    "LOGIN_LOCKOUT_RESET_AFTER": 86400,  # quiet seconds after a lock before durations reset
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
