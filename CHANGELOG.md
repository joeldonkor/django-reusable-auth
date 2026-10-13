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
- `POST /auth/logout/`: blacklists a refresh token. Requires
  `rest_framework_simplejwt.token_blacklist` (checked as `reusable_auth.E002`).
- `GET /auth/me/`: returns the authenticated user.
- `reusable_auth.conf` module holding all package settings and their defaults.
- Session management: `GET /auth/sessions/` lists active sessions,
  `DELETE /auth/sessions/<id>/` revokes one, `DELETE /auth/sessions/` logs out
  everywhere.
- Refresh token reuse detection: reusing a rotated refresh token revokes all of
  the user's sessions. Configured with `REFRESH_TOKEN_REUSE_GRACE`.
- System check `reusable_auth.W003` when refresh token rotation is off.

### Changed

- **Breaking:** login now returns `{"access": ..., "refresh": ...}` at the top
  level, matching the refresh endpoint, instead of nesting them under `"tokens"`.
- **Breaking:** wrong credentials now return `401 {"detail": ...}` instead of
  `400 {"error": ...}`. All errors use DRF's standard format.
- **Breaking:** `login_user()` raises `InvalidCredentials` instead of `ValueError`,
  and `AccountLocked` (a DRF `Throttled`) instead of `AccountLockedError`.
- Success messages use the `"detail"` key instead of `"message"`.
- Public endpoints no longer depend on the host project's `REST_FRAMEWORK`
  authentication and permission defaults.
- The token refresh URL now uses `ThrottledTokenRefreshView`.

## [0.1.0]

### Added

- Custom email-based user model.
- JWT registration, login and token refresh endpoints.
