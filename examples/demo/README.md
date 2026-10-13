# django-reusable-auth demo

A minimal Django project using the package, with interactive API docs. Use it
to try the endpoints, or as a reference for your own settings: every setting
the package needs is marked with `reusable_auth` in `demo/settings.py`.

## Run it

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[openapi]"

cd examples/demo
python manage.py migrate
python manage.py runserver
```

Open <http://localhost:8000/api/docs/> for Swagger UI.

## Try the flow

1. **Register:** `POST /api/auth/register/`. The verification email is printed
   in the `runserver` terminal.
2. **Verify:** copy `uid` and `token` from the link in that email into
   `POST /api/auth/email/verify/`. There's no frontend here, so the link itself
   goes nowhere.
3. **Log in:** `POST /api/auth/login/` returns an access and a refresh token.
4. **Authorize:** click **Authorize** in Swagger UI and paste the access token
   to call `/api/auth/me/`, `/api/auth/sessions/` and the other protected
   endpoints.

Password reset works the same way: request it, then copy `uid` and `token` from
the printed email into `POST /api/auth/password/reset/confirm/`.

The Django admin is at <http://localhost:8000/admin/> after
`python manage.py createsuperuser`.

> This project is for local use only: `DEBUG` is on and the secret key is public.
