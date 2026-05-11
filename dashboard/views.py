from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from bookings.services import (
    get_current_balance,
    get_planned_income,
    get_planned_expenses,
    get_available_funds,
    get_due_this_month
)
from bookings.models import Booking
from alerts.models import Alert
from datetime import date


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
