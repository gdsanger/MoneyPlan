"""
Business logic services for bookings app.

All monetary values are Decimal. All dates are datetime.date.
Positive amounts = income, negative amounts = expenses.
"""
from decimal import Decimal
from datetime import date
from calendar import monthrange
from django.db.models import Sum, Q, QuerySet
from .models import Booking, Category, Liability, Asset


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
    When month is None (Gesamt), also includes unbilled time entries.

    Args:
        month: Optional date representing a calendar month. If given, scope to that month.
               If None, include all future planned bookings and unbilled time entries.

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

        # Add unbilled time entries to Gesamt (only when month is None)
        try:
            from timetracking.services import get_unbilled_total
            planned_income += get_unbilled_total()
        except ImportError:
            pass

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


def get_planned_carry_forward(year: int, month: int) -> Decimal:
    """
    Sum of all bookings (both `booked` and `planned`) with date < first day of given month.
    This is the planned carry-forward balance for the monthly view.

    Args:
        year: Year of the target month
        month: Month number (1-12)

    Returns:
        Decimal: Planned carry-forward balance (booked + planned)
    """
    first_day = date(year, month, 1)
    result = Booking.objects.filter(date__lt=first_day).aggregate(total=Sum('amount'))
    return result['total'] or Decimal('0.00')


def get_previous_month_cumulative_result(year: int, month: int) -> Decimal:
    """
    Calculate the cumulative result (income + expenses) for all bookings
    up to the end of the previous month.

    Args:
        year: Year of the target month
        month: Month number (1-12)

    Returns:
        Decimal: Cumulative result up to end of previous month
    """
    first_day = date(year, month, 1)
    # Get all bookings before the current month
    result = Booking.objects.filter(date__lt=first_day).aggregate(total=Sum('amount'))
    return result['total'] or Decimal('0.00')


def get_previous_month_end_balance(year: int, month: int) -> Decimal:
    """
    Calculate the end balance at the end of the previous month.
    This is equivalent to the cumulative result of all bookings before the current month.

    Args:
        year: Year of the target month
        month: Month number (1-12)

    Returns:
        Decimal: End balance at end of previous month
    """
    # For now, this is the same as previous_month_cumulative_result
    # Both represent the cumulative sum of all bookings before the current month
    return get_previous_month_cumulative_result(year, month)


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
    Also injects virtual time tracking forecast entry if unbilled entries exist.

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
                'timetracking_amount': Decimal('...'),  # optional, if time tracking entry in this month
                'timetracking_date': date(...),  # optional
            }
    """
    # Lazy import to avoid circular dependency
    try:
        from timetracking.services import get_forecast_entry
        tt_entry = get_forecast_entry()
    except ImportError:
        tt_entry = None

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

        # Check if time tracking entry falls in this month
        month_data = {
            'month': first_day,
            'label': f"{month_names[target_month - 1]} {target_year}",
            'planned_income': monthly_income,
            'planned_expenses': monthly_expenses,
        }

        if tt_entry and tt_entry['date'].year == target_year and tt_entry['date'].month == target_month:
            # Inject time tracking entry into this month
            monthly_income += tt_entry['amount']
            month_data['timetracking_amount'] = tt_entry['amount']
            month_data['timetracking_date'] = tt_entry['date']

        # Update running balance
        running_balance = running_balance + monthly_income - monthly_expenses
        month_data['projected_balance'] = running_balance

        forecast_data.append(month_data)

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


def get_year_overview(year: int) -> list[dict]:
    """
    Return overview data for all 12 months of a given year.

    Args:
        year: The year to generate overview for

    Returns:
        list[dict]: List of 12 dicts (one per month) with structure:
            {
                'month': 1,
                'label': 'Januar',
                'year': 2025,
                'income_booked': Decimal('...'),
                'income_planned': Decimal('...'),
                'expenses_booked': Decimal('...'),     # positive number
                'expenses_planned': Decimal('...'),    # positive number
                'result_booked': Decimal('...'),       # income - expenses (booked only)
                'result_total': Decimal('...'),        # including planned
                'booking_count': 12,
                'is_future': bool,                     # True if month is in the future
                'is_current': bool,                    # True if current month
            }
    """
    today = date.today()

    # German month names
    month_names = [
        'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
        'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'
    ]

    result = []

    for month in range(1, 13):
        first_day = date(year, month, 1)
        last_day = date(year, month, monthrange(year, month)[1])

        # Determine if month is future or current
        is_future = first_day > today
        is_current = (year == today.year and month == today.month)

        # Get booked income for this month
        income_booked_qs = Booking.objects.filter(
            status='booked',
            amount__gt=0,
            date__gte=first_day,
            date__lte=last_day
        )
        income_booked = income_booked_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # Get planned income for this month
        income_planned_qs = Booking.objects.filter(
            status='planned',
            amount__gt=0,
            date__gte=first_day,
            date__lte=last_day
        )
        income_planned = income_planned_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # Get booked expenses for this month (as positive number)
        expenses_booked_qs = Booking.objects.filter(
            status='booked',
            amount__lt=0,
            date__gte=first_day,
            date__lte=last_day
        )
        expenses_booked_total = expenses_booked_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        expenses_booked = abs(expenses_booked_total)

        # Get planned expenses for this month (as positive number)
        expenses_planned_qs = Booking.objects.filter(
            status='planned',
            amount__lt=0,
            date__gte=first_day,
            date__lte=last_day
        )
        expenses_planned_total = expenses_planned_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        expenses_planned = abs(expenses_planned_total)

        # Calculate results
        result_booked = income_booked - expenses_booked
        result_total = (income_booked + income_planned) - (expenses_booked + expenses_planned)

        # Get booking count for this month
        booking_count = Booking.objects.filter(
            date__gte=first_day,
            date__lte=last_day
        ).count()

        result.append({
            'month': month,
            'label': month_names[month - 1],
            'year': year,
            'income_booked': income_booked,
            'income_planned': income_planned,
            'expenses_booked': expenses_booked,
            'expenses_planned': expenses_planned,
            'result_booked': result_booked,
            'result_total': result_total,
            'booking_count': booking_count,
            'is_future': is_future,
            'is_current': is_current,
        })

    return result


def get_total_liabilities() -> Decimal:
    """
    Sum of `remaining` across all liabilities where `remaining > 0`.

    Returns:
        Decimal: Total outstanding liabilities
    """
    total = Decimal('0.00')
    for liability in Liability.objects.all():
        if liability.remaining > 0:
            total += liability.remaining
    return total


def get_liabilities_overview() -> list[dict]:
    """
    Return overview data for all liabilities with calculated statistics.

    Returns:
        list[dict]: List of dicts with structure:
            {
                'liability': Liability object,
                'total_repaid': Decimal,
                'remaining': Decimal,
                'repaid_percent': int,
                'is_closed': bool,
                'monthly_avg': Decimal,  # avg monthly repayment based on linked bookings
            }
    """
    liabilities = Liability.objects.all()
    result = []

    for liability in liabilities:
        # Calculate monthly average repayment
        linked_bookings = liability.bookings.filter(amount__lt=0)
        booking_count = linked_bookings.count()

        if booking_count > 0:
            total_repaid = liability.total_repaid
            monthly_avg = total_repaid / booking_count
        else:
            monthly_avg = Decimal('0.00')

        result.append({
            'liability': liability,
            'total_repaid': liability.total_repaid,
            'remaining': liability.remaining,
            'repaid_percent': liability.repaid_percent,
            'is_closed': liability.is_closed,
            'monthly_avg': monthly_avg,
        })

    return result


def get_total_assets() -> Decimal:
    """
    Sum of `current_value` across all assets.

    Returns:
        Decimal: Total asset value
    """
    result = Asset.objects.aggregate(total=Sum('current_value'))
    return result['total'] or Decimal('0.00')


def get_net_worth() -> Decimal:
    """
    Calculate net worth: total assets − total liabilities.

    Returns:
        Decimal: Net worth (total assets minus outstanding liabilities)
    """
    total_assets = get_total_assets()
    total_liabilities = get_total_liabilities()
    return total_assets - total_liabilities


def get_assets_by_category() -> list[dict]:
    """
    Return assets grouped by category with totals and percentages.

    Returns:
        list[dict]: List of dicts with structure:
            {
                'category': 'real_estate',
                'label': 'Immobilien',
                'total': Decimal('...'),
                'count': 2,
                'percent': 65.4,   # share of total assets
            }
    """
    from django.db import models as django_models

    # Get total assets for percentage calculation
    total_assets = get_total_assets()

    if total_assets == 0:
        return []

    # Get assets grouped by category
    category_data = Asset.objects.values('category').annotate(
        total=Sum('current_value'),
        count=django_models.Count('id')
    ).order_by('-total')

    result = []
    for item in category_data:
        # Get the label from ASSET_CATEGORY_CHOICES
        category_label = dict(Asset.ASSET_CATEGORY_CHOICES).get(
            item['category'],
            item['category']
        )

        percent = float((item['total'] / total_assets) * 100)

        result.append({
            'category': item['category'],
            'label': category_label,
            'total': item['total'],
            'count': item['count'],
            'percent': round(percent, 1),
        })

    return result


