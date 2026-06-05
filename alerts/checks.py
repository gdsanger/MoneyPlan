"""
Alert checking functions for the alerts app.
"""
from datetime import date, timedelta
from decimal import Decimal
from django.conf import settings
from django.db.models import Q
from .models import Alert, AlertConfig
from bookings.models import Booking
from bookings.services import get_forecast


def run_all_checks() -> dict:
    """
    Run all enabled alert checks and return a summary.

    Returns:
        dict: Summary with keys 'created', 'skipped_dedup', 'mail_sent', 'errors'
    """
    config = AlertConfig.get()

    created = 0
    skipped_dedup = 0
    mail_sent = 0
    errors = 0

    # Run due soon check
    if config.alert_due_enabled:
        try:
            result = check_due_soon(config)
            created += result
        except Exception as e:
            errors += 1
            print(f"Error in check_due_soon: {e}")

    # Run overdue check
    if config.alert_overdue_enabled:
        try:
            result = check_overdue(config)
            created += result
        except Exception as e:
            errors += 1
            print(f"Error in check_overdue: {e}")

    # Run liquidity check
    if config.alert_liquidity_enabled:
        try:
            result = check_liquidity(config)
            created += result
        except Exception as e:
            errors += 1
            print(f"Error in check_liquidity: {e}")

    # Count how many alerts were skipped due to dedup
    # (This is approximate - we count existing alerts that match current bookings)
    today = date.today()
    due_date = today + timedelta(days=config.days_before_due)

    # Count existing due_soon alerts that would have been created
    if config.alert_due_enabled:
        due_bookings = Booking.objects.filter(
            status='planned',
            date__gte=today,
            date__lte=due_date
        ).count()
        existing_due = Alert.objects.filter(
            alert_type='due_soon',
            booking__status='planned',
            booking__date__gte=today,
            booking__date__lte=due_date
        ).count()
        skipped_dedup += max(0, existing_due)

    # Count existing overdue alerts
    if config.alert_overdue_enabled:
        overdue_bookings = Booking.objects.filter(
            status='planned',
            date__lt=today
        ).count()
        existing_overdue = Alert.objects.filter(
            alert_type='overdue',
            booking__status='planned',
            booking__date__lt=today
        ).count()
        skipped_dedup += max(0, existing_overdue)

    # Note: mail_sent would need to be tracked during alert creation
    # For now, we just count how many alerts have mail_sent=True that were created today
    mail_sent = Alert.objects.filter(
        mail_sent=True,
        created_at__date=today
    ).count()

    return {
        'created': created,
        'skipped_dedup': skipped_dedup,
        'mail_sent': mail_sent,
        'errors': errors
    }


def check_due_soon(config: AlertConfig) -> int:
    """
    For each `planned` booking where date is within the next config.days_before_due days:
    - Compute dedup_key = f"due_soon_{booking.id}_{booking.date}"
    - If key not in Alert table → create Alert, send mail if SMTP configured
    - Return count of new alerts created

    Args:
        config: AlertConfig instance

    Returns:
        int: Number of new alerts created
    """
    today = date.today()
    due_date = today + timedelta(days=config.days_before_due)

    due_bookings = Booking.objects.filter(
        status='planned',
        date__gte=today,
        date__lte=due_date
    )

    created_count = 0

    for booking in due_bookings:
        dedup_key = f"due_soon_{booking.id}_{booking.date}"

        # Check if alert already exists
        if Alert.objects.filter(dedup_key=dedup_key).exists():
            continue

        # Create new alert
        message = f"Buchung '{booking.description}' ist fällig am {booking.date} (Betrag: {booking.amount} €)"

        alert = Alert.objects.create(
            alert_type='due_soon',
            booking=booking,
            message=message,
            dedup_key=dedup_key
        )

        # Try to send email if SMTP is configured
        if config.smtp_host and config.alert_email:
            from .mailer import send_alert_mail
            try:
                if send_alert_mail(alert, config):
                    alert.mail_sent = True
                    alert.save()
            except Exception as e:
                print(f"Failed to send alert email: {e}")

        created_count += 1

    return created_count


def check_overdue(config: AlertConfig) -> int:
    """
    For each `planned` booking where date < today:
    - dedup_key = f"overdue_{booking.id}"
    - Create Alert if not exists

    Args:
        config: AlertConfig instance

    Returns:
        int: Number of new alerts created
    """
    today = date.today()

    overdue_bookings = Booking.objects.filter(
        status='planned',
        date__lt=today
    )

    created_count = 0

    for booking in overdue_bookings:
        dedup_key = f"overdue_{booking.id}"

        # Check if alert already exists
        if Alert.objects.filter(dedup_key=dedup_key).exists():
            continue

        # Create new alert
        days_overdue = (today - booking.date).days
        message = f"Buchung '{booking.description}' ist überfällig seit {days_overdue} Tag(en) (Fälligkeitsdatum: {booking.date}, Betrag: {booking.amount} €)"

        alert = Alert.objects.create(
            alert_type='overdue',
            booking=booking,
            message=message,
            dedup_key=dedup_key
        )

        # Try to send email if SMTP is configured
        if config.smtp_host and config.alert_email:
            from .mailer import send_alert_mail
            try:
                if send_alert_mail(alert, config):
                    alert.mail_sent = True
                    alert.save()
            except Exception as e:
                print(f"Failed to send alert email: {e}")

        created_count += 1

    return created_count


def check_liquidity(config: AlertConfig) -> int:
    """
    Get forecast for the configured horizon. If any month's projected_balance < config.liquidity_threshold:
    - dedup_key = f"liquidity_{date.today().isoformat()}"
    - Create Alert with details of which month(s) are critical

    Args:
        config: AlertConfig instance

    Returns:
        int: Number of new alerts created (0 or 1)
    """
    forecast = get_forecast(months=settings.FORECAST_MONTHS)

    # Find months with balance below threshold
    critical_months = []
    for month_data in forecast:
        if month_data['projected_balance'] < config.liquidity_threshold:
            critical_months.append(month_data)

    # If no critical months, no alert needed
    if not critical_months:
        return 0

    # Create dedup key based on today's date
    today = date.today()
    dedup_key = f"liquidity_{today.isoformat()}"

    # Check if alert already exists for today
    if Alert.objects.filter(dedup_key=dedup_key).exists():
        return 0

    # Build message listing all critical months
    month_details = []
    for month_data in critical_months:
        month_details.append(
            f"{month_data['label']}: {month_data['projected_balance']} € "
            f"(Schwelle: {config.liquidity_threshold} €)"
        )

    message = (
        f"Liquiditätsengpass prognostiziert! "
        f"Folgende Monate unterschreiten die Schwelle:\n" +
        "\n".join(month_details)
    )

    alert = Alert.objects.create(
        alert_type='liquidity',
        booking=None,  # No specific booking
        message=message,
        dedup_key=dedup_key
    )

    # Try to send email if SMTP is configured
    if config.smtp_host and config.alert_email:
        from .mailer import send_alert_mail
        try:
            if send_alert_mail(alert, config):
                alert.mail_sent = True
                alert.save()
        except Exception as e:
            print(f"Failed to send alert email: {e}")

    return 1


def cleanup_resolved_alerts() -> int:
    """
    Remove `due_soon` and `overdue` alerts whose booking is now `booked` (condition resolved).

    Returns:
        int: Count of alerts removed
    """
    # Find alerts where the booking is now booked (no longer planned)
    resolved_alerts = Alert.objects.filter(
        Q(alert_type='due_soon') | Q(alert_type='overdue'),
        booking__isnull=False,
        booking__status='booked'
    )

    count = resolved_alerts.count()
    resolved_alerts.delete()

    return count
