from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from bookings.services import (
    get_current_balance,
    get_planned_income,
    get_planned_expenses,
    get_available_funds,
    get_due_this_month,
    get_year_overview
)
from bookings.models import Booking
from alerts.models import Alert
from datetime import date
from decimal import Decimal


@login_required
def index(request):
    """Dashboard Hauptansicht"""
    today = date.today()

    # KPI data
    current_balance = get_current_balance()
    planned_income = get_planned_income()
    planned_expenses = get_planned_expenses()
    available_funds_month = get_available_funds(month=today)
    available_funds_total = get_available_funds()

    # Active alerts count
    active_alerts_count = Alert.objects.count()

    # Due bookings for the table
    due_bookings = get_due_this_month()

    context = {
        'current_balance': current_balance,
        'planned_income': planned_income,
        'planned_expenses': planned_expenses,
        'available_funds_month': available_funds_month,
        'available_funds_total': available_funds_total,
        'active_alerts_count': active_alerts_count,
        'due_bookings': due_bookings,
        'today': today,
    }

    return render(request, 'dashboard/index.html', context)


@login_required
def mark_as_booked(request, booking_id):
    """
    Mark a booking as booked via HTMX.
    Returns updated table row HTML.
    """
    if request.method == 'POST':
        booking = get_object_or_404(Booking, pk=booking_id)
        booking.status = 'booked'
        booking.save()

        # Return updated row HTML
        context = {
            'booking': booking,
            'today': date.today(),
        }
        return render(request, 'dashboard/_booking_row.html', context)

    return HttpResponse(status=405)


@login_required
def year_overview(request, year=None):
    """
    Year overview with 12-month heatmap.
    Shows income, expenses, and result for each month.
    """
    today = date.today()

    # Default to current year if not specified
    if year is None:
        year = today.year

    # Get year overview data
    months_data = get_year_overview(year)

    # Calculate year summary statistics
    total_income = sum(m['income_booked'] for m in months_data)
    total_expenses = sum(m['expenses_booked'] for m in months_data)
    total_result = total_income - total_expenses
    avg_per_month = total_result / Decimal('12') if months_data else Decimal('0.00')

    # Find best and worst months (by booked result)
    best_month = max(months_data, key=lambda m: m['result_booked']) if months_data else None
    worst_month = min(months_data, key=lambda m: m['result_booked']) if months_data else None

    # Calculate color scale based on min/max results
    min_result = min(m['result_booked'] for m in months_data) if months_data else Decimal('0.00')
    max_result = max(m['result_booked'] for m in months_data) if months_data else Decimal('0.00')

    # Add color intensity to each month
    for month_data in months_data:
        result = month_data['result_booked']
        if result > 0:
            # Positive: scale from 0.1 to 0.35
            if max_result > 0:
                intensity = 0.1 + (result / max_result) * 0.25
            else:
                intensity = 0.1
            month_data['bg_color'] = f'rgba(25, 135, 84, {intensity:.2f})'
        elif result < 0:
            # Negative: scale from 0.1 to 0.35
            if min_result < 0:
                intensity = 0.1 + (abs(result) / abs(min_result)) * 0.25
            else:
                intensity = 0.1
            month_data['bg_color'] = f'rgba(220, 53, 69, {intensity:.2f})'
        else:
            # Zero or no data: default background
            month_data['bg_color'] = None

    context = {
        'year': year,
        'prev_year': year - 1,
        'next_year': year + 1,
        'months_data': months_data,
        'total_income': total_income,
        'total_expenses': total_expenses,
        'total_result': total_result,
        'avg_per_month': avg_per_month,
        'best_month': best_month,
        'worst_month': worst_month,
        'today': today,
    }

    # For HTMX requests, return only the grid partial
    if request.htmx:
        return render(request, 'dashboard/_year_grid.html', context)

    return render(request, 'dashboard/year_overview.html', context)
