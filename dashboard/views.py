from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db import models
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
from tasks.models import Task
from datetime import date, timedelta
from decimal import Decimal


def get_kpi_context():
    """Helper function to get KPI context data for dashboard"""
    today = date.today()

    # Task counts
    overdue_tasks_count = Task.objects.filter(
        status='open',
        due_date__lt=today
    ).count()

    return {
        'current_balance': get_current_balance(),
        'planned_income': get_planned_income(),
        'planned_expenses': get_planned_expenses(),
        'available_funds_month': get_available_funds(month=today),
        'available_funds_total': get_available_funds(),
        'active_alerts_count': Alert.objects.count(),
        'overdue_tasks_count': overdue_tasks_count,
        'today': today,
    }


@login_required
def index(request):
    """Dashboard Hauptansicht"""
    # Get KPI data
    context = get_kpi_context()

    # Due bookings for the table
    context['due_bookings'] = get_due_this_month()

    # Open tasks for dashboard widget (max 5)
    # Show: overdue first, then due soon, then by priority
    today = date.today()
    overdue_tasks = Task.objects.filter(
        status='open',
        due_date__lt=today
    ).order_by('due_date', '-priority')

    due_soon_tasks = Task.objects.filter(
        status='open',
        due_date__gte=today,
        due_date__lte=today + timedelta(days=3)
    ).order_by('due_date', '-priority')

    other_open_tasks = Task.objects.filter(
        status='open'
    ).filter(
        models.Q(due_date__isnull=True) | models.Q(due_date__gt=today + timedelta(days=3))
    ).order_by('due_date', '-priority')

    # Combine and limit to 5
    from itertools import chain
    open_tasks = list(chain(overdue_tasks, due_soon_tasks, other_open_tasks))[:5]
    context['open_tasks'] = open_tasks

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

    # Calculate year summary statistics (including planned bookings)
    total_income = sum(m['income_booked'] + m['income_planned'] for m in months_data)
    total_expenses = sum(m['expenses_booked'] + m['expenses_planned'] for m in months_data)
    total_result = total_income - total_expenses
    avg_per_month = total_result / Decimal('12') if months_data else Decimal('0.00')

    # Find best and worst months (by total result including planned)
    best_month = max(months_data, key=lambda m: m['result_total']) if months_data else None
    worst_month = min(months_data, key=lambda m: m['result_total']) if months_data else None

    # Calculate color scale based on min/max results (using result_total)
    min_result = min(m['result_total'] for m in months_data) if months_data else Decimal('0.00')
    max_result = max(m['result_total'] for m in months_data) if months_data else Decimal('0.00')

    # Add color intensity to each month
    for month_data in months_data:
        result = month_data['result_total']
        if result > 0:
            # Positive: scale from 0.1 to 0.35
            if max_result > 0:
                intensity = 0.1 + float(result / max_result) * 0.25
            else:
                intensity = 0.1
            # Reduce opacity for future months (forecast)
            if month_data['is_future']:
                intensity = intensity * 0.6
            month_data['bg_color'] = f'rgba(25, 135, 84, {intensity:.2f})'
        elif result < 0:
            # Negative: scale from 0.1 to 0.35
            if min_result < 0:
                intensity = 0.1 + float(abs(result) / abs(min_result)) * 0.25
            else:
                intensity = 0.1
            # Reduce opacity for future months (forecast)
            if month_data['is_future']:
                intensity = intensity * 0.6
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
