from django.core.management.base import BaseCommand

from accounts.lockout import cleanup_stale_attempts


class Command(BaseCommand):
    help = "Remove stale sign-in attempts without clearing active lockouts"

    def handle(self, *args, **options):
        # Delete expired login attempt records
        cleanup_stale_attempts()

        self.stdout.write(
            self.style.SUCCESS("Stale login attempts cleaned up.")
        )
