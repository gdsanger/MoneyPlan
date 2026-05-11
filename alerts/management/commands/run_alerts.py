from django.core.management.base import BaseCommand
from django.utils import timezone
from alerts.models import Alert, AlertConfig
from bookings.models import Booking
from datetime import timedelta


class Command(BaseCommand):
    help = 'Run alert checks for due bookings and liquidity'

    def handle(self, *args, **options):
        config = AlertConfig.get_config()
        today = timezone.now().date()

        self.stdout.write(self.style.SUCCESS(f'Running alert checks for {today}'))

        # Check for due soon alerts
        if config.alert_due_enabled:
            due_date = today + timedelta(days=config.days_before_due)
            due_bookings = Booking.objects.filter(
                date__lte=due_date,
                date__gte=today,
                status='planned'
            )

            for booking in due_bookings:
                dedup_key = f"due_soon_{booking.id}_{booking.date}"
                if not Alert.objects.filter(dedup_key=dedup_key).exists():
                    Alert.objects.create(
                        alert_type='due_soon',
                        booking=booking,
                        message=f"Buchung '{booking.description}' ist fällig am {booking.date}",
                        dedup_key=dedup_key
                    )
                    self.stdout.write(f"Created due_soon alert for booking {booking.id}")

        # Check for overdue alerts
        if config.alert_overdue_enabled:
            overdue_bookings = Booking.objects.filter(
                date__lt=today,
                status='planned'
            )

            for booking in overdue_bookings:
                dedup_key = f"overdue_{booking.id}"
                if not Alert.objects.filter(dedup_key=dedup_key).exists():
                    Alert.objects.create(
                        alert_type='overdue',
                        booking=booking,
                        message=f"Buchung '{booking.description}' ist überfällig (Fälligkeitsdatum: {booking.date})",
                        dedup_key=dedup_key
                    )
                    self.stdout.write(f"Created overdue alert for booking {booking.id}")

        # TODO: Implement liquidity check

        self.stdout.write(self.style.SUCCESS('Alert checks completed'))
