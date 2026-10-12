# Roadmap

Work through these **in order**, top to bottom. Each step builds on the ones before it,
and the "Needs" line says which earlier steps it depends on.
Tick a box when the step's "Done when" is true and the test suite passes.

---

## First release plan (v0.1.0) — Fri 9 Oct to Mon 12 Oct 2026

Goal: an installable, documented, tested and reasonably secure package.
The rest of the roadmap (steps 13+) continues at a steady pace afterwards.

| Day | Steps | Outcome |
|---|---|---|
| **Fri 9 Oct** | 1–3 | Clean tests, migrations, `pyproject.toml` — the package installs |
| **Sat 10 Oct** | 4–6 | Working sandbox project, admin support, README setup guide |
| **Sun 11 Oct** | 7–10 | CI on GitHub, linting/coverage, login fix, rate limiting |
| **Mon 12 Oct** | 11–12 *(optional)* | `/auth/me/` and logout |

**Release checklist (end of Monday):**
- [ ] All tests pass locally and CI is green
- [ ] README setup guide works in a fresh sandbox project
- [ ] Version in `pyproject.toml` is `0.1.0`
- [ ] Tag the release: `git tag v0.1.0` and `git push --tags`
- [ ] *(Stretch)* Upload to TestPyPI and install from there

If a day overruns, move its unfinished steps to the next day and drop steps 11–12 —
don't skip understanding to stay on schedule.

---

## Stage 1 — Make the package installable

### [ ] 1. Clean up the existing tests
- **Do:** Remove the `print` statements from `src/tests/test_models.py`.
- **Learn:** Why tests should use assertions, not printed output.
- **Done when:** `python tests/runtests.py` shows no printed output besides the test results.

### [ ] 2. Create migrations
- **Needs:** —
- **Do:** Run `makemigrations reusable_auth` and commit the `migrations/` folder.
- **Learn:** What migrations are, and why a reusable app must ship its own.
  Tests pass without them only because Django builds tables directly for apps with no migrations.
- **Done when:** `src/reusable_auth/migrations/0001_initial.py` exists, includes the
  `unique_lower_email` constraint, and the tests still pass.

### [ ] 3. Add `pyproject.toml`
- **Needs:** 2
- **Do:** Add package name, version (`0.1.0`), Python version, and dependencies
  (Django, djangorestframework, djangorestframework-simplejwt) with sensible version ranges.
- **Learn:** Python packaging, the `src/` layout, dependency version ranges.
- **Read:** https://packaging.python.org/en/latest/tutorials/packaging-projects/
- **Done when:** `pip install -e .` works from the repo root.

### [ ] 4. Install it into a throwaway Django project
- **Needs:** 3
- **Do:** Create a new Django project somewhere else, `pip install -e` your package into it,
  wire it up, and register/log in with a real HTTP client (curl, Postman, or httpie).
  Write down every problem you hit.
- **Learn:** What a user of your package experiences.
- **Done when:** You can register, log in and refresh a token in the sandbox project.

### [ ] 5. Admin support
- **Needs:** 4 (you'll see the admin break in the sandbox)
- **Do:** Add `admin.py` registering `CustomUser`. Django's `UserAdmin` assumes a `username`
  field, so you'll need to customise `ordering`, `fieldsets`, `add_fieldsets`, and the forms.
- **Learn:** `UserAdmin`, `UserCreationForm`, `UserChangeForm`.
- **Done when:** You can create, edit and search users in the sandbox project's admin.

### [ ] 6. README setup guide
- **Needs:** 4, 5
- **Do:** Document installation, `INSTALLED_APPS` (including `token_blacklist`),
  `AUTH_USER_MODEL` (must be set **before** the project's first migration),
  `include()`-ing the URLs, and the `SIMPLE_JWT` settings. Use your notes from step 4.
- **Done when:** Following only the README, you can set the package up in a *new* sandbox project.

---

## Stage 2 — Automate quality checks

Set this up now, so every feature after it is checked automatically.

### [ ] 7. CI with GitHub Actions
- **Needs:** 3 (CI needs to know what to install)
- **Do:** Add `.github/workflows/tests.yml` that runs the tests on every push,
  for Python 3.12–3.14.
- **Read:** https://docs.github.com/en/actions/automating-builds-and-tests/building-and-testing-python
- **Done when:** You see a green tick on GitHub, and a deliberately broken test turns it red.

### [ ] 8. Linting and coverage
- **Needs:** 7
- **Do:** Add `ruff` (linting/formatting) and `coverage.py`; run both in CI.
- **Learn:** How to read a coverage report and find untested branches.
- **Done when:** CI runs ruff and coverage, and `services.py` shows 100% branch coverage.

---

## Stage 3 — Security hardening

### [ ] 9. Fix the login serializer
- **Needs:** —
- **Do:** Remove `min_length=8` from the login password field.
- **Learn:** Why login must not enforce registration rules (it leaks your password policy and
  can lock out accounts created under older, weaker rules).
- **Done when:** A test proves a short wrong password gets the same "Invalid email or password"
  response as any other wrong password.

### [ ] 10. Rate limiting
- **Needs:** —
- **Do:** Throttle the login and registration endpoints.
- **Learn:** DRF throttling, especially `ScopedRateThrottle`, and the cache it relies on.
- **Done when:** A test shows the N+1th rapid login attempt gets HTTP 429.

---

## Stage 4 — Core account features

### [ ] 11. `GET /auth/me/`
- **Needs:** —
- **Do:** Return the logged-in user using `UserSerializer`.
- **Learn:** `IsAuthenticated`, and how `JWTAuthentication` turns a `Bearer` token into `request.user`.
  This is the simplest authenticated endpoint, so it teaches the pattern used by steps 12–14.
- **Done when:** Tests cover a valid token (200), a missing token (401) and an expired token (401).

### [ ] 12. Logout
- **Needs:** 11
- **Do:** `POST /auth/logout/` blacklists the given refresh token.
- **Learn:** Why access tokens can't be revoked (they're stateless until they expire)
  and what the blacklist is for.
- **Done when:** After logout, the refresh token can no longer be used to get a new access token.

### [ ] 13. Update profile
- **Needs:** 11
- **Do:** `PATCH /auth/me/` lets users change their own first and last name.
- **Learn:** Partial updates, and which fields users must never set themselves
  (`is_staff`, `is_superuser`, `is_active`, `email` without re-verification).
- **Done when:** A test proves sending `"is_staff": true` doesn't make the user staff.

### [ ] 14. Change password
- **Needs:** 11, 12
- **Do:** Require the old password; validate the new one with `validate_password`.
- **Decide:** Should existing refresh tokens be blacklisted after a change? (Use what you learned in 12.)
- **Done when:** Wrong old password → 400; weak new password → 400; success → can log in with the new password only.

### [ ] 15. Email sending setup
- **Needs:** —
- **Do:** Add a small `send_email` helper in `services.py`; in tests use Django's `locmem` email
  backend, in the sandbox use the `console` backend.
- **Learn:** `EMAIL_BACKEND`, `django.core.mail`, `mail.outbox` in tests.
- **Done when:** A test can assert an email was "sent" and read its content.

### [ ] 16. Email verification
- **Needs:** 15
- **Do:** Send a verification link on registration; add a verify endpoint.
- **Learn:** Signed tokens (`django.core.signing` or `PasswordResetTokenGenerator`), and
  `is_active` vs. a separate `email_verified` field (needs a new migration — see step 2).
- **Bonus:** Registering an existing email can now *email the owner* instead of silently doing nothing,
  closing the enumeration gap left in registration.
- **Done when:** Unverified users can't log in (or can — your choice, documented in the README).

### [ ] 17. Password reset
- **Needs:** 15, 16 (same token technique)
- **Do:** "Request reset" endpoint emails a link; "confirm reset" endpoint sets the new password.
- **Learn:** Why "request reset" must respond identically whether or not the email exists.
- **Done when:** Tests cover the full flow, expired/used tokens, and unknown emails.

---

## Stage 5 — Make it a good reusable package

### [ ] 18. Configurable settings
- **Needs:** 16 (you now have real options to configure, e.g. "require email verification")
- **Do:** Read options from a `REUSABLE_AUTH = {...}` dict in the host project's settings, with defaults.
- **Learn:** Read `rest_framework_simplejwt/settings.py` in your `.venv` — it's a good pattern to copy.
- **Done when:** Tests use `override_settings` to prove each option changes behaviour.

### [ ] 19. Swappable serializers
- **Needs:** 18
- **Do:** Let projects point a setting at their own registration serializer (to add fields like phone number).
- **Learn:** `django.utils.module_loading.import_string`.
- **Done when:** A test swaps in a custom serializer with an extra field.

### [ ] 20. API documentation
- **Needs:** 11–17 (document the finished endpoints)
- **Do:** Add optional `drf-spectacular` support and describe it in the README.
- **Done when:** The sandbox project shows all your endpoints in Swagger UI.

---

## Stage 6 — Release

### [ ] 21. Test multiple Django versions with tox
- **Needs:** 7
- **Do:** Add `tox.ini` covering the Django versions you claim to support in `pyproject.toml`; run tox in CI.
- **Read:** https://tox.wiki/en/latest/user_guide.html, and the `tox.ini` in
  https://github.com/jazzband/djangorestframework-simplejwt
- **Done when:** CI passes on every combination.

### [ ] 22. Versioning and CHANGELOG
- **Needs:** —
- **Do:** Add `CHANGELOG.md`; adopt semantic versioning.
- **Learn:** Why "registration no longer returns tokens" is a breaking change.
- **Done when:** Every user-facing change since the start is listed.

### [ ] 23. Publish
- **Needs:** everything above
- **Do:** Build with `python -m build`, upload to **TestPyPI** first, install from there into a
  fresh sandbox, then publish to PyPI.
- **Done when:** `pip install <your-package-name>` works anywhere.

---

## Using Claude without skipping the learning

For each step:

1. **Plan before coding:** "I'm on step 12 (logout). Explain how blacklisting works and what pieces
   I need. Don't write the code."
2. **Write it yourself.** Stuck? Ask for a *hint*: "My test gets 401 — give me a hint where to look."
3. **Get a review:** "Review my change for bugs and security issues, but let me fix them."
4. **Tests:** Write some yourself, then ask "What cases did I miss?"
5. **Explain it back:** "Here's how I think this works — am I right?"

Fine to hand off: boilerplate you already understand, git chores, explaining tracebacks,
finding the right docs page, and comparing your approach with how mature packages solve it.

Rule of thumb: if you paste in code you couldn't explain line by line, ask for a walkthrough first.

