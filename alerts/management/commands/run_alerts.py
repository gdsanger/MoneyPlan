from django.core.management.base import BaseCommand
from alerts.models import AlertConfig
from alerts.checks import run_all_checks, cleanup_resolved_alerts


class Command(BaseCommand):
    help = 'Run alert checks for due bookings and liquidity'

    def handle(self, *args, **options):
        # Load configuration
        config = AlertConfig.get()

        self.stdout.write(self.style.SUCCESS('Running alert checks...'))

        # Run all checks
        summary = run_all_checks()

        # Cleanup resolved alerts
        cleaned = cleanup_resolved_alerts()

        # Print summary
        self.stdout.write(self.style.SUCCESS(
            f"Alert checks completed:\n"
            f"  - Created: {summary['created']}\n"
            f"  - Skipped (dedup): {summary['skipped_dedup']}\n"
            f"  - Mail sent: {summary['mail_sent']}\n"
            f"  - Errors: {summary['errors']}\n"
            f"  - Cleaned up: {cleaned}"
        ))
