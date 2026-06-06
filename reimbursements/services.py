"""Business logic for ISARtec expense reimbursements."""
from datetime import date
from decimal import Decimal

from .models import ExpenseClaim


def get_unreimbursed_claims():
    """All claims not yet reimbursed."""
    return ExpenseClaim.objects.filter(
        status__in=[ExpenseClaim.STATUS_PENDING, ExpenseClaim.STATUS_SUBMITTED]
    )


def get_pending_claims():
    """Claims ready for submission."""
    return ExpenseClaim.objects.filter(status=ExpenseClaim.STATUS_PENDING).order_by('date')


def get_unreimbursed_total() -> Decimal:
    """Sum of amounts for all unreimbursed claims."""
    claims = get_unreimbursed_claims()
    total = sum(claim.amount for claim in claims)
    return Decimal(str(total)) if total else Decimal('0.00')


def get_forecast_entry() -> dict | None:
    """
    Virtual forecast entry for unreimbursed expense claims.

    Payment date = 15th of next month (same rule as time tracking).
    """
    total = get_unreimbursed_total()
    if total == 0:
        return None

    today = date.today()
    if today.month == 12:
        payment_date = date(today.year + 1, 1, 15)
    else:
        payment_date = date(today.year, today.month + 1, 15)

    return {
        'date': payment_date,
        'description': 'Auslagenerstattung ISARtec (offen)',
        'amount': total,
        'source': 'reimbursements',
    }
