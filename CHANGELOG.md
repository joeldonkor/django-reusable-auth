# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.1] - 2026-10-13

### Changed

- Shorter package summary on PyPI. No code changes.

## [1.0.0] - 2026-10-13

First release on PyPI.

### Added

- Email-based user model with case-insensitive emails.
- Endpoints for registration, login, logout, token refresh and the current user.
- Email verification, required by default (`REQUIRE_EMAIL_VERIFICATION`), with
  a resend endpoint.
- Password change and password reset. Both log out every session and notify the
  user by email.
- Session management: list active sessions, revoke one, or log out everywhere.
- Account deactivation, which revokes every session, including when a user is
  deactivated outside the API.
- Refresh token reuse detection: reusing a rotated refresh token revokes all of
  the user's sessions.
- Per-IP rate limiting on the public endpoints, password change and
  deactivation, configurable per scope.
- Account lockout after repeated failed logins, doubling in length on each
  repeat, and the `unlock_account` management command.
- Registration, verification resend and password reset respond the same way
  for every email, so they don't reveal which emails are registered.
- Overridable email templates, and the `EMAIL_SENDER` setting for sending
  emails another way.
- System checks for insecure or incomplete configuration
  (`reusable_auth.E001`–`E003`, `W001`–`W004`).
- OpenAPI schema annotations, used when drf-spectacular is installed
  (`django-reusable-auth[openapi]`).
- Example project in `examples/demo`.

### Changes from 0.1.0

0.1.0 was never published to PyPI. If you used it from GitHub:

- Login returns `access` and `refresh` at the top level instead of under
  `tokens`.
- Wrong credentials return 401 instead of 400, and errors use DRF's standard
  format (`detail` instead of `error`).
- Unverified users can't log in until they verify their email. Migration
  `0002` marks existing users as verified.

## 0.1.0

Initial development version, not published.

### Added

- Custom email-based user model.
- JWT registration, login and token refresh endpoints.

[Unreleased]: https://github.com/joeldonkor/django-reusable-auth/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/joeldonkor/django-reusable-auth/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/joeldonkor/django-reusable-auth/releases/tag/v1.0.0
