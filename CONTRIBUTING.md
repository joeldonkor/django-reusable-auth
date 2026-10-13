# Contributing

Thanks for helping! Bug reports, fixes and improvements are all welcome. For a
security issue, follow [SECURITY.md](SECURITY.md) instead of opening an issue.

## Setup

```bash
git clone https://github.com/joeldonkor/django-reusable-auth.git
cd django-reusable-auth
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[test]"
```

## Checks

CI runs all of these, so run them before opening a pull request:

```bash
flake8 src tests     # lint
pytest --cov         # tests, failing below 95% coverage
```

Locally the tests use SQLite and Django's in-memory cache. CI also runs them
against Redis and PostgreSQL; to do that yourself, set `REDIS_URL` and/or
`POSTGRES_HOST` (plus `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`) and
install `redis` / `psycopg[binary]`.

The [demo project](examples/demo) is the quickest way to try a change by hand.

## Adding or changing an endpoint

Each endpoint follows the same rules. Check your change against them:

- [ ] **Explicit auth:** subclass `PublicAPIView` or `AuthenticatedAPIView` in
      `views.py`, never plain `APIView`, so the host project's DRF defaults
      can't break it.
- [ ] **Throttle scope:** add one in `throttles.py` with a sensible default.
- [ ] **No account discovery:** a public endpoint taking an email must respond
      the same way whether or not the account exists.
- [ ] **Errors:** raise DRF exceptions (see `exceptions.py`); don't build error
      responses by hand.
- [ ] **OpenAPI:** add `@extend_schema(...)`. `tests/test_schema.py` fails on
      undocumented endpoints.
- [ ] **Settings:** new settings go in `conf.py` with a default.
- [ ] **Tests:** cover the success path, each error and any security property.
- [ ] **Docs:** update the README and add a line under "Unreleased" in
      [CHANGELOG.md](CHANGELOG.md).

## Commits and pull requests

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
(`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `ci:`), with `!` for breaking
changes. Keep a pull request to one change and explain why it's needed.

## Releasing (maintainers)

1. Move the "Unreleased" changelog entries under a new version with today's date.
2. Set `version` in `pyproject.toml` to match.
3. Optional rehearsal: run the `release` workflow by hand from the Actions tab.
   It publishes to [TestPyPI](https://test.pypi.org/project/django-reusable-auth/).
   TestPyPI never accepts the same version twice either.
4. Commit, then create a GitHub release with a tag like `v1.2.0`. The `release`
   workflow checks the tag matches `pyproject.toml`, builds the package and
   publishes it to PyPI.

### One-time setup

Publishing uses [trusted publishing](https://docs.pypi.org/trusted-publishers/),
so no API token is stored in GitHub.

1. On PyPI (and TestPyPI, which is a separate account), add a trusted publisher
   for project `django-reusable-auth`: owner `joeldonkor`, repository
   `django-reusable-auth`, workflow `release.yaml`, environment `pypi`
   (`testpypi` on TestPyPI). Before the first release, add it as a "pending
   publisher" from your account's Publishing page.
2. In the GitHub repository settings, create the environments `pypi` and
   `testpypi`. Adding yourself as a required reviewer on `pypi` means every
   release waits for your approval before publishing.
