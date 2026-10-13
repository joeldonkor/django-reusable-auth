from django.core.management.base import BaseCommand

from reusable_auth.security import unlock_account


class Command(BaseCommand):
    help = "Clear the login lockout and failed-attempt history for one or more emails."

    def add_arguments(self, parser):
        parser.add_argument("emails", nargs="+", metavar="email")

    def handle(self, *args, emails, **options):
        for email in emails:
            if unlock_account(email):
                self.stdout.write(self.style.SUCCESS(f"Unlocked {email}"))
            else:
                # History is still cleared, so the next lock starts from the base duration
                self.stdout.write(f"{email} was not locked (failure history cleared)")
