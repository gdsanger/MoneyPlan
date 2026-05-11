from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from datetime import date, datetime
from calendar import monthrange
from decimal import Decimal
from .models import Booking, Category, RecurringSeries
from .forms import BookingForm, BookingFilterForm, RecurringSeriesForm
from .services import get_monthly_carry_forward, get_bookings_for_month
from .wizard import preview_series_bookings, create_series_bookings


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

    # Check for series filter (from query params, not in form)
    series_id = request.GET.get('series')
    if series_id:
        try:
            bookings = bookings.filter(series_id=int(series_id))
        except (ValueError, TypeError):
            pass

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
    series = RecurringSeries.objects.select_related('category').all().order_by('-created_at')

    # Annotate with booking count
    series_with_counts = []
    for s in series:
        booking_count = s.bookings.count()
        series_with_counts.append({
            'series': s,
            'booking_count': booking_count,
        })

    context = {
        'series_with_counts': series_with_counts,
    }

    return render(request, 'bookings/series_list.html', context)


@login_required
def series_wizard(request):
    """Step 1: Konfiguration der Serie"""
    if request.method == 'POST':
        form = RecurringSeriesForm(request.POST)
        if form.is_valid():
            # Save form data to session
            request.session['series_form_data'] = {
                'description': form.cleaned_data['description'],
                'amount': str(form.cleaned_data['amount']),
                'interval': form.cleaned_data['interval'],
                'start_date': form.cleaned_data['start_date'].isoformat(),
                'end_date': form.cleaned_data['end_date'].isoformat() if form.cleaned_data['end_date'] else None,
                'category_id': form.cleaned_data['category'].id,
                'notes': form.cleaned_data['notes'],
            }
            return redirect('bookings:series_preview')
    else:
        # Check if we have form data in session (back button from step 2)
        if 'series_form_data' in request.session:
            form_data = request.session['series_form_data']
            # Reconstruct form from session data
            initial_data = {
                'description': form_data['description'],
                'amount': form_data['amount'],
                'interval': form_data['interval'],
                'start_date': datetime.fromisoformat(form_data['start_date']).date(),
                'end_date': datetime.fromisoformat(form_data['end_date']).date() if form_data['end_date'] else None,
                'category': form_data['category_id'],
                'notes': form_data['notes'],
            }
            form = RecurringSeriesForm(initial=initial_data)
        else:
            form = RecurringSeriesForm()

    context = {
        'form': form,
        'step': 1,
    }

    return render(request, 'bookings/series_wizard_step1.html', context)


@login_required
def series_preview(request):
    """Step 2: Vorschau der Buchungen"""
    # Check if we have series data in session
    if 'series_form_data' not in request.session:
        return redirect('bookings:series_wizard')

    if request.method == 'POST':
        # Back button pressed
        if 'back' in request.POST:
            return redirect('bookings:series_wizard')
        # Continue to confirmation
        return redirect('bookings:series_confirm')

    # Build temporary series object for preview
    form_data = request.session['series_form_data']
    series = RecurringSeries(
        description=form_data['description'],
        amount=Decimal(form_data['amount']),
        interval=form_data['interval'],
        start_date=datetime.fromisoformat(form_data['start_date']).date(),
        end_date=datetime.fromisoformat(form_data['end_date']).date() if form_data['end_date'] else None,
        category_id=form_data['category_id'],
        notes=form_data['notes'],
    )

    # Get preview dates
    preview_dates = preview_series_bookings(series)
    booking_count = len(preview_dates)
    show_warning = booking_count > 60

    # Get category for display
    category = Category.objects.get(id=form_data['category_id'])

    context = {
        'series': series,
        'category': category,
        'preview_dates': preview_dates,
        'booking_count': booking_count,
        'show_warning': show_warning,
        'step': 2,
    }

    return render(request, 'bookings/series_wizard_step2.html', context)


@login_required
def series_confirm(request):
    """Step 3: Bestätigung und Anlegen der Serie"""
    if request.method != 'POST':
        return redirect('bookings:series_wizard')

    # Check if we have series data in session
    if 'series_form_data' not in request.session:
        return redirect('bookings:series_wizard')

    # Create the series
    form_data = request.session['series_form_data']
    series = RecurringSeries.objects.create(
        description=form_data['description'],
        amount=Decimal(form_data['amount']),
        interval=form_data['interval'],
        start_date=datetime.fromisoformat(form_data['start_date']).date(),
        end_date=datetime.fromisoformat(form_data['end_date']).date() if form_data['end_date'] else None,
        category_id=form_data['category_id'],
        notes=form_data['notes'],
    )

    # Create all bookings
    created_bookings = create_series_bookings(series)

    # Clear session data
    del request.session['series_form_data']

    # Add success message
    messages.success(
        request,
        f'Serie "{series.description}" erfolgreich angelegt. Es wurden {len(created_bookings)} Buchungen erstellt.'
    )

    return redirect('bookings:series_list')


@login_required
def series_delete(request, series_id):
    """Lösche eine Serie und alle verknüpften Buchungen"""
    if request.method != 'POST':
        return HttpResponse(status=405)

    series = get_object_or_404(RecurringSeries, pk=series_id)

    # Count bookings before deletion
    booking_count = series.bookings.count()
    series_description = series.description

    # Delete the series (bookings will be set to NULL due to SET_NULL)
    # But we should manually delete them for cascade
    series.bookings.all().delete()
    series.delete()

    # Add success message
    messages.success(
        request,
        f'Serie "{series_description}" und {booking_count} verknüpfte Buchungen wurden gelöscht.'
    )

    return redirect('bookings:series_list')



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
