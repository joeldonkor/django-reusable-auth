from django.apps import apps
from django.db.models.signals import post_save
from django.dispatch import receiver

from reusable_auth.models import CustomUser


@receiver(post_save, sender=CustomUser)
def revoke_sessions_of_inactive_user(sender, instance, **kwargs):
    # simplejwt already refuses to refresh tokens of an inactive user, but only
    # while the user stays inactive. Revoking them means reactivating the account
    # later doesn't bring old sessions (including any stolen token) back to life.
    # Runs on every save, so deactivation from the Django admin or a shell is
    # covered too, not just the deactivate endpoint.
    if instance.is_active or not apps.is_installed("rest_framework_simplejwt.token_blacklist"):
        return
    from reusable_auth.services import revoke_all_sessions

    revoke_all_sessions(instance)
