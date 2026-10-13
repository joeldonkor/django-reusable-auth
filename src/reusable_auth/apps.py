from django.apps import AppConfig


class ReusableAuthConfig(AppConfig):
    name = "reusable_auth"
    # Matches 0001_initial, so host projects with a different DEFAULT_AUTO_FIELD
    # don't get a spurious migration for this app
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from reusable_auth import checks  # noqa: F401  (importing registers the checks)
