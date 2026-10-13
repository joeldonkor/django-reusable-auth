# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Per-IP rate limiting on the login, register and token refresh endpoints
  (`429 Too Many Requests` with a `Retry-After` header), with
  defaults that can be changed through `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`.
- Per-email account lockout after repeated failed logins, with progressive
  durations that double on each repeat lockout. Configured through `REUSABLE_AUTH`.
- `unlock_account` management command and `reusable_auth.security.unlock_account()`.
- System checks: `reusable_auth.E001` (DummyCache disables rate limiting),
  `reusable_auth.W001` (LocMemCache in production) and `reusable_auth.W002`
  (unknown `REUSABLE_AUTH` setting).
- Lockout events logged on the `reusable_auth.security` logger.
- CI job that runs the test suite against Redis.

### Changed

- The token refresh URL now uses `ThrottledTokenRefreshView`.

## [0.1.0]

### Added

- Custom email-based user model.
- JWT registration, login and token refresh endpoints.
