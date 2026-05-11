from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.contrib import messages
from datetime import date, datetime
from .models import Booking, Category
from .forms import BookingForm, BookingFilterForm, CategoryForm


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
    """Liste aller Kategorien mit Buchungsanzahl"""
    # Get all categories with booking count
    categories = Category.objects.annotate(
        booking_count=Count('bookings')
    ).order_by('name')

    context = {
        'categories': categories,
    }

    return render(request, 'bookings/category_list.html', context)


@login_required
def category_create(request):
    """Erstelle eine neue Kategorie"""
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()

            # If HTMX request, redirect to reload the page
            if request.htmx:
                response = HttpResponse('')
                response['HX-Redirect'] = request.META.get('HTTP_REFERER', '/kategorien/')
                return response

            messages.success(request, f'Kategorie "{category.name}" wurde erstellt.')
            return redirect('bookings:categories')
    else:
        form = CategoryForm()

    context = {'form': form}

    # If HTMX request, return only the form
    if request.htmx:
        return render(request, 'bookings/_category_form.html', context)

    return render(request, 'bookings/category_form.html', context)


@login_required
def category_edit(request, category_id):
    """Bearbeite eine Kategorie"""
    category = get_object_or_404(Category, pk=category_id)

    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            category = form.save()

            # If HTMX request, redirect to reload the page
            if request.htmx:
                response = HttpResponse('')
                response['HX-Redirect'] = request.META.get('HTTP_REFERER', '/kategorien/')
                return response

            messages.success(request, f'Kategorie "{category.name}" wurde aktualisiert.')
            return redirect('bookings:categories')
    else:
        form = CategoryForm(instance=category)

    context = {
        'form': form,
        'category': category,
    }

    # If HTMX request, return only the form
    if request.htmx:
        return render(request, 'bookings/_category_form.html', context)

    return render(request, 'bookings/category_form.html', context)


@login_required
def category_delete(request, category_id):
    """Lösche eine Kategorie"""
    if request.method != 'POST':
        return HttpResponse(status=405)

    category = get_object_or_404(Category, pk=category_id)

    # Check if category has bookings
    booking_count = category.bookings.count()
    if booking_count > 0:
        # Return error message
        if request.htmx:
            return HttpResponse(
                f'<div class="alert alert-danger">Kategorie kann nicht gelöscht werden. '
                f'Es sind noch {booking_count} Buchung{"en" if booking_count != 1 else ""} dieser Kategorie zugeordnet.</div>',
                status=400
            )
        messages.error(
            request,
            f'Kategorie "{category.name}" kann nicht gelöscht werden. '
            f'Es sind noch {booking_count} Buchung{"en" if booking_count != 1 else ""} dieser Kategorie zugeordnet.'
        )
        return redirect('bookings:categories')

    category_name = category.name
    category.delete()

    # If HTMX request, return empty response (row will be removed)
    if request.htmx:
        return HttpResponse('')

    messages.success(request, f'Kategorie "{category_name}" wurde gelöscht.')
    return redirect('bookings:categories')


@login_required
def series_list(request):
    """Liste aller wiederkehrenden Serien"""
    return render(request, 'bookings/series_list.html')
