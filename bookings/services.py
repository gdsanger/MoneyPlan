"""
Business logic services for bookings app.

All monetary values are Decimal. All dates are datetime.date.
Positive amounts = income, negative amounts = expenses.
"""
from decimal import Decimal
from datetime import date
from calendar import monthrange
from django.db.models import Sum, Q, QuerySet
from .models import Booking, Category


def get_current_balance() -> Decimal:
    """
    Sum of all `booked` bookings. This is the actual current balance.

    Returns:
        Decimal: Current balance (positive = surplus, negative = deficit)
    """
    result = Booking.objects.filter(status='booked').aggregate(total=Sum('amount'))
    return result['total'] or Decimal('0.00')


def get_planned_income(until: date = None) -> Decimal:
    """
    Sum of all `planned` bookings with positive amount.

    Args:
        until: Optional date limit. If given, only include bookings up to that date.

    Returns:
        Decimal: Total planned income
    """
    queryset = Booking.objects.filter(status='planned', amount__gt=0)
    if until:
        queryset = queryset.filter(date__lte=until)
    result = queryset.aggregate(total=Sum('amount'))
    return result['total'] or Decimal('0.00')


def get_planned_expenses(until: date = None) -> Decimal:
    """
    Sum of all `planned` bookings with negative amount.

    Args:
        until: Optional date limit. If given, only include bookings up to that date.

    Returns:
        Decimal: Total planned expenses (returned as positive number for display)
    """
    queryset = Booking.objects.filter(status='planned', amount__lt=0)
    if until:
        queryset = queryset.filter(date__lte=until)
    result = queryset.aggregate(total=Sum('amount'))
    total = result['total'] or Decimal('0.00')
    return abs(total)  # Return as positive for display


def get_available_funds(month: date = None) -> Decimal:
    """
    Calculate available funds: current_balance + planned_income - planned_expenses.

    Args:
        month: Optional date representing a calendar month. If given, scope to that month.
               If None, include all future planned bookings.

    Returns:
        Decimal: Available funds projection
    """
    current_balance = get_current_balance()

    if month:
        # Get first and last day of the month
        first_day = date(month.year, month.month, 1)
        last_day = date(month.year, month.month, monthrange(month.year, month.month)[1])

        planned_income = get_planned_income(until=last_day)
        planned_expenses = get_planned_expenses(until=last_day)
    else:
        # All future planned bookings
        planned_income = get_planned_income()
        planned_expenses = get_planned_expenses()

    return current_balance + planned_income - planned_expenses


def get_monthly_carry_forward(year: int, month: int) -> Decimal:
    """
    Sum of all `booked` bookings with date < first day of given month.
    This is the carry-forward balance (Saldovortrag) for the monthly view.

    Args:
        year: Year of the target month
        month: Month number (1-12)

    Returns:
        Decimal: Carry-forward balance
    """
    first_day = date(year, month, 1)
    result = Booking.objects.filter(status='booked', date__lt=first_day).aggregate(total=Sum('amount'))
    return result['total'] or Decimal('0.00')


def get_bookings_for_month(year: int, month: int) -> QuerySet:
    """
    Return all bookings for the given month, ordered by date, id.
    Includes both `booked` and `planned` bookings.

    Args:
        year: Year of the target month
        month: Month number (1-12)

    Returns:
        QuerySet: Bookings for the specified month
    """
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])

    return Booking.objects.filter(
        date__gte=first_day,
        date__lte=last_day
    ).order_by('date', 'id')


def get_due_this_month() -> QuerySet:
    """
    All `planned` bookings where date is between today and end of current month.

    Returns:
        QuerySet: Due bookings ordered by date
    """
    today = date.today()
    last_day = date(today.year, today.month, monthrange(today.year, today.month)[1])

    return Booking.objects.filter(
        status='planned',
        date__gte=today,
        date__lte=last_day
    ).order_by('date')


def get_forecast(months: int = 3) -> list[dict]:
    """
    Return a list of dicts, one per month (current + next `months` months).

    Logic: start from get_current_balance(), then for each month add all planned bookings.

    Args:
        months: Number of future months to forecast (default: 3)

    Returns:
        list[dict]: List of monthly projections with structure:
            {
                'month': date(2025, 1, 1),  # first day of that month
                'label': 'Jan 2025',
                'projected_balance': Decimal('...'),
                'planned_income': Decimal('...'),
                'planned_expenses': Decimal('...'),
            }
    """
    today = date.today()
    current_balance = get_current_balance()
    forecast_data = []

    # German month names
    month_names = [
        'Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun',
        'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'
    ]

    running_balance = current_balance

    for i in range(months + 1):  # +1 to include current month
        # Calculate target month
        target_month = today.month + i
        target_year = today.year

        # Handle year overflow
        while target_month > 12:
            target_month -= 12
            target_year += 1

        first_day = date(target_year, target_month, 1)
        last_day = date(target_year, target_month, monthrange(target_year, target_month)[1])

        # Get planned income and expenses for this month
        monthly_income_qs = Booking.objects.filter(
            status='planned',
            amount__gt=0,
            date__gte=first_day,
            date__lte=last_day
        )
        monthly_income_result = monthly_income_qs.aggregate(total=Sum('amount'))
        monthly_income = monthly_income_result['total'] or Decimal('0.00')

        monthly_expenses_qs = Booking.objects.filter(
            status='planned',
            amount__lt=0,
            date__gte=first_day,
            date__lte=last_day
        )
        monthly_expenses_result = monthly_expenses_qs.aggregate(total=Sum('amount'))
        monthly_expenses_total = monthly_expenses_result['total'] or Decimal('0.00')
        monthly_expenses = abs(monthly_expenses_total)  # Positive for display

        # Update running balance
        running_balance = running_balance + monthly_income - monthly_expenses

        # Format label
        label = f"{month_names[target_month - 1]} {target_year}"

        forecast_data.append({
            'month': first_day,
            'label': label,
            'projected_balance': running_balance,
            'planned_income': monthly_income,
            'planned_expenses': monthly_expenses,
        })

    return forecast_data


def get_top_categories(limit: int = 10, months_back: int = 3) -> list[dict]:
    """
    Return top expense categories by total absolute amount over the last months_back months.

    Args:
        limit: Maximum number of categories to return (default: 10)
        months_back: Number of months to look back (default: 3)

    Returns:
        list[dict]: List of dicts with structure:
            [{'category': Category, 'total': Decimal('...')}, ...]
    """
    today = date.today()

    # Calculate the date months_back months ago
    target_month = today.month - months_back
    target_year = today.year

    while target_month <= 0:
        target_month += 12
        target_year -= 1

    start_date = date(target_year, target_month, 1)

    # Get expenses (negative amounts) from the period
    expenses = Booking.objects.filter(
        date__gte=start_date,
        date__lte=today,
        amount__lt=0
    ).values('category').annotate(
        total=Sum('amount')
    ).order_by('total')  # Most negative first

    # Convert to list of dicts with Category objects and positive totals
    result = []
    for item in expenses[:limit]:
        try:
            category = Category.objects.get(pk=item['category'])
            result.append({
                'category': category,
                'total': abs(item['total'])  # Positive for display
            })
        except Category.DoesNotExist:
            continue

    return result
