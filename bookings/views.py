from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from datetime import date, datetime
from calendar import monthrange
from decimal import Decimal
from .models import Booking, Category
from .forms import BookingForm, BookingFilterForm
from .services import get_monthly_carry_forward, get_bookings_for_month


@login_required
def booking_list(request):
    """Liste aller Buchungen mit Filtern und Pagination"""
    # Get all bookings
    bookings = Booking.objects.select_related('category', 'series').all()

    # Apply filters
    filter_form = BookingFilterForm(request.GET)
    if filter_form.is_valid():
        status = filter_form.cleaned_data.get('status')
        booking_type = filter_form.cleaned_data.get('type')
        category = filter_form.cleaned_data.get('category')
        month = filter_form.cleaned_data.get('month')

        if status:
            bookings = bookings.filter(status=status)

        if booking_type == 'income':
            bookings = bookings.filter(amount__gte=0)
        elif booking_type == 'expense':
            bookings = bookings.filter(amount__lt=0)

        if category:
            bookings = bookings.filter(category=category)

        if month:
            # Parse month input (YYYY-MM)
            bookings = bookings.filter(
                date__year=month.year,
                date__month=month.month
            )

    # Order by date descending
    bookings = bookings.order_by('-date', '-id')

    # Pagination
    paginator = Paginator(bookings, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'today': date.today(),
    }

    # If HTMX request, return only the list partial
    if request.htmx:
        return render(request, 'bookings/_booking_list.html', context)

    return render(request, 'bookings/booking_list.html', context)


@login_required
def booking_create(request):
    """Erstelle eine neue Buchung"""
    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save()

            # If HTMX request, return the new row
            if request.htmx:
                context = {
                    'booking': booking,
                    'today': date.today(),
                }
                response = render(request, 'bookings/_booking_row.html', context)
                # Trigger a page reload to refresh the list
                response['HX-Redirect'] = request.META.get('HTTP_REFERER', '/buchungen/')
                return response

            return redirect('bookings:list')
    else:
        form = BookingForm()

    context = {'form': form}

    # If HTMX request, return only the form
    if request.htmx:
        return render(request, 'bookings/_booking_form.html', context)

    return render(request, 'bookings/booking_form.html', context)


@login_required
def booking_edit(request, booking_id):
    """Bearbeite eine Buchung"""
    booking = get_object_or_404(Booking, pk=booking_id)

    if request.method == 'POST':
        form = BookingForm(request.POST, instance=booking)
        if form.is_valid():
            booking = form.save()

            # If HTMX request, return the updated row
            if request.htmx:
                context = {
                    'booking': booking,
                    'today': date.today(),
                }
                response = render(request, 'bookings/_booking_row.html', context)
                # Trigger a page reload to refresh the list
                response['HX-Redirect'] = request.META.get('HTTP_REFERER', '/buchungen/')
                return response

            return redirect('bookings:list')
    else:
        form = BookingForm(instance=booking)

    context = {
        'form': form,
        'booking': booking,
    }

    # If HTMX request, return only the form
    if request.htmx:
        return render(request, 'bookings/_booking_form.html', context)

    return render(request, 'bookings/booking_form.html', context)


@login_required
def booking_delete(request, booking_id):
    """Lösche eine Buchung"""
    if request.method != 'POST':
        return HttpResponse(status=405)

    booking = get_object_or_404(Booking, pk=booking_id)
    booking.delete()

    # If HTMX request, return empty response (row will be removed)
    if request.htmx:
        return HttpResponse('')

    return redirect('bookings:list')


@login_required
def booking_toggle_status(request, booking_id):
    """Toggle Buchungsstatus zwischen geplant und gebucht"""
    if request.method != 'POST':
        return HttpResponse(status=405)

    booking = get_object_or_404(Booking, pk=booking_id)

    # Toggle status
    if booking.status == 'planned':
        booking.status = 'booked'
    else:
        booking.status = 'planned'

    booking.save()

    # Return updated row
    context = {
        'booking': booking,
        'today': date.today(),
    }
    return render(request, 'bookings/_booking_row.html', context)


@login_required
def category_list(request):
    """Liste aller Kategorien"""
    return render(request, 'bookings/category_list.html')


@login_required
def series_list(request):
    """Liste aller wiederkehrenden Serien"""
    return render(request, 'bookings/series_list.html')


@login_required
def month_view(request, year=None, month=None):
    """Monatsansicht aller Buchungen mit Saldovortrag und laufendem Saldo"""
    # Default to current month
    today = date.today()
    if year is None or month is None:
        year = today.year
        month = today.month

    # Validate month and year
    try:
        year = int(year)
        month = int(month)
        if not (1 <= month <= 12):
            raise ValueError
        # Test if date is valid
        first_day = date(year, month, 1)
    except (ValueError, TypeError):
        year = today.year
        month = today.month
        first_day = date(year, month, 1)

    # Get carry forward balance (all booked bookings before this month)
    carry_forward = get_monthly_carry_forward(year, month)

    # Get all bookings for this month
    bookings = get_bookings_for_month(year, month).select_related('category', 'series')

    # Calculate running balance and month totals
    running_balance = carry_forward
    month_income = Decimal('0.00')
    month_expenses = Decimal('0.00')

    # Build list of bookings with running balance
    bookings_with_balance = []
    for booking in bookings:
        # Only include booked bookings in running balance
        if booking.status == 'booked':
            running_balance += booking.amount

        # Calculate month income and expenses (both booked and planned)
        if booking.amount >= 0:
            month_income += booking.amount
        else:
            month_expenses += booking.amount

        bookings_with_balance.append({
            'booking': booking,
            'running_balance': running_balance if booking.status == 'booked' else None,
        })

    month_result = month_income + month_expenses
    end_balance = carry_forward + month_result

    # Calculate previous and next month
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1

    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1

    # German month names
    month_names = [
        'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
        'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'
    ]
    month_label = f"{month_names[month - 1]} {year}"

    context = {
        'year': year,
        'month': month,
        'month_label': month_label,
        'carry_forward': carry_forward,
        'month_income': month_income,
        'month_expenses': month_expenses,
        'month_result': month_result,
        'end_balance': end_balance,
        'bookings_with_balance': bookings_with_balance,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'today': today,
    }

    # If HTMX request, return only the month content partial
    if request.htmx:
        return render(request, 'bookings/_month_content.html', context)

    return render(request, 'bookings/month_view.html', context)
