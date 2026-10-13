import logging

from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils.module_loading import import_string

from reusable_auth.conf import get_setting
from reusable_auth.security import hash_email
from reusable_auth.tokens import email_verification_token, encode_uid, password_reset_token

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Sending
# -----------------------------------------------------------------------------
#
# Each email has a "kind" (verify_email, password_reset, ...) and is rendered
# from templates/reusable_auth/email/<kind>_subject.txt and <kind>_body.txt,
# plus <kind>_body.html if it exists. A host project changes the wording by
# putting a file at the same path in its own templates folder, or replaces
# sending entirely (e.g. to queue it in Celery) with REUSABLE_AUTH["EMAIL_SENDER"].

def send_templated_email(kind, user, context):
    """The default EMAIL_SENDER: render the templates and send with Django's mail backend."""
    prefix = f"reusable_auth/email/{kind}"
    # Subjects must be one line; a stray newline from the template breaks the header
    subject = " ".join(render_to_string(f"{prefix}_subject.txt", context).split())
    message = EmailMultiAlternatives(subject, render_to_string(f"{prefix}_body.txt", context), to=[user.email])
    try:
        message.attach_alternative(render_to_string(f"{prefix}_body.html", context), "text/html")
    except TemplateDoesNotExist:
        pass  # plain text only
    message.send()


def _send(kind, user, **context):
    # Don't email the same address again within EMAIL_COOLDOWN. IP throttling
    # alone doesn't stop someone flooding one inbox from many IPs.
    cooldown_key = f"reusable_auth:email_cooldown:{kind}:{hash_email(user.email)}"
    if not cache.add(cooldown_key, True, timeout=get_setting("EMAIL_COOLDOWN")):
        return

    sender = import_string(get_setting("EMAIL_SENDER"))
    try:
        sender(kind=kind, user=user, context={"user": user, **context})
    except Exception:
        # Never let a mail failure become a 500. Password reset answers the same
        # way for known and unknown emails; a crash only for known ones would
        # reveal which emails have accounts.
        logger.exception("Failed to send %s email to user_id=%s", kind, user.pk)


def _link(setting, uid, token):
    url = get_setting(setting)
    return url.format(uid=uid, token=token) if url else None


# -----------------------------------------------------------------------------
# Emails
# -----------------------------------------------------------------------------

def send_verification_email(user):
    uid, token = encode_uid(user), email_verification_token.make_token(user)
    _send("verify_email", user, uid=uid, token=token, link=_link("EMAIL_VERIFICATION_URL", uid, token))


def send_password_reset_email(user):
    uid, token = encode_uid(user), password_reset_token.make_token(user)
    _send("password_reset", user, uid=uid, token=token, link=_link("PASSWORD_RESET_URL", uid, token))


def send_password_changed_email(user):
    # Lets the real owner notice if someone else changed their password
    _send("password_changed", user)


def send_account_exists_email(user):
    # Sent when someone registers with an email that already has an account. The
    # API response is the same as for a new signup, so only the inbox owner learns
    # the account exists.
    _send("account_exists", user)
