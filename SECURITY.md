# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.x | Yes |
| < 1.0 | No |

## Reporting a vulnerability

**Please don't report security issues in public GitHub issues, discussions or pull requests.**

Report them privately through GitHub:
[**Report a vulnerability**](https://github.com/joeldonkor/django-reusable-auth/security/advisories/new)

Please include:

* the version of django-reusable-auth, Django, DRF and simplejwt you're using
* what an attacker can do, and the steps or code to reproduce it
* any relevant settings (`REUSABLE_AUTH`, `SIMPLE_JWT`, cache backend)

You'll get an acknowledgement within 7 days. Once the issue is confirmed, a fix
is prepared privately and released with a GitHub security advisory crediting
you, unless you'd rather stay anonymous.

## Security model

What the package protects against, and how, is documented in the
[README](README.md): rate limiting and account lockout, refresh token rotation
with reuse detection, single-use emailed links, and responses that don't reveal
which emails are registered.

Some limits are inherent to the design and aren't vulnerabilities:

* **Access tokens can't be revoked.** Logout, session revocation, password
  changes and deactivation all revoke refresh tokens; an access token already
  issued stays valid until it expires. Keep `ACCESS_TOKEN_LIFETIME` short.
* **Anyone who knows an email can trigger its login lockout.** Lockouts expire
  and IP throttling limits how fast they can be caused.
* **Sending email during a request can leak timing.** See "Email setup" in the
  README for queuing emails instead.
* **Rate limiting depends on a shared cache.** With `LocMemCache`, limits are
  per process. The package warns about this at startup (`reusable_auth.W001`).
