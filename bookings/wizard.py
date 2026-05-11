"""
Recurring series wizard functions for creating and previewing bookings.
"""
from datetime import date, timedelta
from calendar import monthrange
from typing import List
from .models import RecurringSeries, Booking


def preview_series_bookings(series: RecurringSeries) -> List[date]:
    """
    Return a list of dates that would be created for the given series.
    Does not write to DB. Used to show the preview step in the wizard.

    Args:
        series: RecurringSeries instance

    Returns:
        List[date]: List of dates that would be generated
    """
    dates = []
    current_date = series.start_date

    # If no end_date, default to 2 years from start
    end_date = series.end_date or (series.start_date + timedelta(days=730))

    # Sanity check: don't generate more than 10 years worth
    max_end_date = series.start_date + timedelta(days=3650)
    if end_date > max_end_date:
        end_date = max_end_date

    while current_date <= end_date:
        dates.append(current_date)
        current_date = _get_next_date(current_date, series.interval, series.start_date)

    return dates


def create_series_bookings(series: RecurringSeries) -> List[Booking]:
    """
    Generate and create all Booking instances for the series.
    Uses bulk_create. Returns the created bookings.

    Skips dates where a booking with identical series, date, and description
    already exists (idempotent).

    Args:
        series: RecurringSeries instance

    Returns:
        List[Booking]: List of created Booking instances
    """
    dates = preview_series_bookings(series)

    # Get existing bookings for this series to avoid duplicates
    existing_bookings = set(
        Booking.objects.filter(
            series=series
        ).values_list('date', 'description')
    )

    # Build list of bookings to create
    bookings_to_create = []
    for booking_date in dates:
        # Check if this exact booking already exists
        if (booking_date, series.description) in existing_bookings:
            continue

        bookings_to_create.append(
            Booking(
                date=booking_date,
                description=series.description,
                amount=series.amount,
                notes=series.notes,
                status='planned',
                category=series.category,
                series=series
            )
        )

    # Bulk create all bookings
    if bookings_to_create:
        created = Booking.objects.bulk_create(bookings_to_create)
        return created

    return []


def _get_next_date(current_date: date, interval: str, start_date: date) -> date:
    """
    Calculate the next date based on the interval.

    Args:
        current_date: Current date in the series
        interval: 'weekly', 'monthly', 'quarterly', 'semi_annual', or 'yearly'
        start_date: Original start date (for reference day)

    Returns:
        date: Next date in the series
    """
    if interval == 'weekly':
        return current_date + timedelta(days=7)

    elif interval == 'monthly':
        # Same day each month, handle month-end edge cases
        next_month = current_date.month + 1
        next_year = current_date.year

        if next_month > 12:
            next_month = 1
            next_year += 1

        # Use the original start_date's day
        target_day = start_date.day

        # Handle months with fewer days (e.g., Jan 31 -> Feb 28/29)
        last_day_of_month = monthrange(next_year, next_month)[1]
        actual_day = min(target_day, last_day_of_month)

        return date(next_year, next_month, actual_day)

    elif interval == 'quarterly':
        # Every 3 months
        next_month = current_date.month + 3
        next_year = current_date.year

        while next_month > 12:
            next_month -= 12
            next_year += 1

        # Use the original start_date's day
        target_day = start_date.day

        # Handle months with fewer days
        last_day_of_month = monthrange(next_year, next_month)[1]
        actual_day = min(target_day, last_day_of_month)

        return date(next_year, next_month, actual_day)

    elif interval == 'semi_annual':
        # Every 6 months
        next_month = current_date.month + 6
        next_year = current_date.year

        while next_month > 12:
            next_month -= 12
            next_year += 1

        # Use the original start_date's day
        target_day = start_date.day

        # Handle months with fewer days (e.g., Aug 31 -> Feb 28/29)
        last_day_of_month = monthrange(next_year, next_month)[1]
        actual_day = min(target_day, last_day_of_month)

        return date(next_year, next_month, actual_day)

    elif interval == 'yearly':
        # Same date each year
        next_year = current_date.year + 1

        # Handle leap year edge case (Feb 29 -> Feb 28)
        target_day = start_date.day
        target_month = start_date.month

        if target_month == 2 and target_day == 29:
            # Check if next year is a leap year
            last_day_of_feb = monthrange(next_year, 2)[1]
            actual_day = min(29, last_day_of_feb)
            return date(next_year, 2, actual_day)

        return date(next_year, target_month, target_day)

    else:
        # Unknown interval, just add 30 days as fallback
        return current_date + timedelta(days=30)
