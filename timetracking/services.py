"""Service functions for time tracking business logic."""
from datetime import date
from decimal import Decimal
from django.db.models import Sum, Count, Q
from .models import TimeEntry, Client


def get_unbilled_total() -> Decimal:
    """
    Sum of `amount` for all `billed=False` entries.

    Returns:
        Decimal: Total unbilled amount
    """
    unbilled = TimeEntry.objects.filter(billed=False)
    total = sum(entry.amount for entry in unbilled)
    return Decimal(str(total)) if total else Decimal('0.00')


def get_unbilled_entries():
    """
    All TimeEntry where billed=False, ordered by date.

    Returns:
        QuerySet: Unbilled time entries
    """
    return TimeEntry.objects.filter(billed=False).select_related('client')


def get_forecast_entry() -> dict | None:
    """
    Returns a virtual forecast entry for unbilled time entries.

    Rule:
    - Take all unbilled entries
    - Projected payment date = 15th of next month
    - Returns dict compatible with forecast display

    Returns None if no unbilled entries exist.
    """
    total = get_unbilled_total()
    if total == 0:
        return None

    today = date.today()
    # Payment always on 15th of next month
    if today.month == 12:
        payment_date = date(today.year + 1, 1, 15)
    else:
        payment_date = date(today.year, today.month + 1, 15)

    return {
        'date': payment_date,
        'description': 'Stundenabrechnung (offen)',
        'amount': total,
        'source': 'timetracking',   # identifies this as a virtual entry
    }


def get_monthly_summary(year: int, month: int) -> dict:
    """
    Get summary of time entries for a specific month.

    Args:
        year: Year
        month: Month (1-12)

    Returns:
        dict with keys:
            - total_hours: Decimal
            - total_amount: Decimal
            - billed_hours: Decimal
            - billed_amount: Decimal
            - unbilled_hours: Decimal
            - unbilled_amount: Decimal
            - entry_count: int
    """
    entries = TimeEntry.objects.filter(
        date__year=year,
        date__month=month
    )

    billed_entries = entries.filter(billed=True)
    unbilled_entries = entries.filter(billed=False)

    total_hours = sum(entry.duration for entry in entries) or Decimal('0.00')
    total_amount = sum(entry.amount for entry in entries) or Decimal('0.00')

    billed_hours = sum(entry.duration for entry in billed_entries) or Decimal('0.00')
    billed_amount = sum(entry.amount for entry in billed_entries) or Decimal('0.00')

    unbilled_hours = sum(entry.duration for entry in unbilled_entries) or Decimal('0.00')
    unbilled_amount = sum(entry.amount for entry in unbilled_entries) or Decimal('0.00')

    return {
        'total_hours': Decimal(str(total_hours)),
        'total_amount': Decimal(str(total_amount)),
        'billed_hours': Decimal(str(billed_hours)),
        'billed_amount': Decimal(str(billed_amount)),
        'unbilled_hours': Decimal(str(unbilled_hours)),
        'unbilled_amount': Decimal(str(unbilled_amount)),
        'entry_count': entries.count(),
    }


def get_client_summary() -> list[dict]:
    """
    Get summary of unbilled hours and amounts per client.

    Returns:
        list of dicts with keys:
            - client: Client instance
            - unbilled_hours: Decimal
            - unbilled_amount: Decimal
            - total_hours_all_time: Decimal
    """
    clients = Client.objects.all()
    result = []

    for client in clients:
        unbilled_entries = client.entries.filter(billed=False)
        all_entries = client.entries.all()

        unbilled_hours = sum(entry.duration for entry in unbilled_entries) or Decimal('0.00')
        unbilled_amount = sum(entry.amount for entry in unbilled_entries) or Decimal('0.00')
        total_hours = sum(entry.duration for entry in all_entries) or Decimal('0.00')

        result.append({
            'client': client,
            'unbilled_hours': Decimal(str(unbilled_hours)),
            'unbilled_amount': Decimal(str(unbilled_amount)),
            'total_hours_all_time': Decimal(str(total_hours)),
        })

    return result
