from django.core.management.base import BaseCommand, CommandError

from delta_feed.accounts.setup import needs_setup, rotate_setup_token


class Command(BaseCommand):
    help = (
        "Rotate the first-run setup token and print it. Use when the server logs "
        "with the original token are lost. Refuses once any user exists."
    )

    def handle(self, *args, **options):
        if not needs_setup():
            raise CommandError("A user already exists; first-run setup is closed.")
        token, row = rotate_setup_token()
        self.stderr.write(f"New setup token (expires {row.expires_at.isoformat()}); older tokens no longer work.")
        self.stdout.write(token)
