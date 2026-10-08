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
* Brute-force protection strategies
* Rate-limiting support
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

## Security

Security is a core requirement of this project.

If you discover a security vulnerability, please do **not** disclose it publicly through a GitHub issue. A dedicated security reporting process will be documented before the first stable release.

> This project does not claim to make applications completely secure. Authentication security depends on correct configuration, deployment practices, dependencies, and the application using the package.

## License

This project will be released under the **MIT License**.

---

**django-reusable-auth**

> Build authentication once. Configure it for every project.
