from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Subquery, OuterRef
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from datetime import date, datetime
from calendar import monthrange
from decimal import Decimal
import magic
from .models import Booking, Category, RecurringSeries
from .forms import BookingForm, BookingFilterForm, RecurringSeriesForm, CategoryForm, QuickBookingForm
from .services import (
    get_monthly_carry_forward,
    get_bookings_for_month,
    get_planned_carry_forward,
    get_previous_month_cumulative_result,
    get_previous_month_end_balance,
)
from .wizard import preview_series_bookings, create_series_bookings
from .receipt_service import recognize_receipt, ReceiptRecognitionResult
from attachments.services import get_attachments_for, handle_upload
from attachments.models import Attachment
from ai.exceptions import AIProviderNotConfigured, AIServiceError, AIResponseParseError


@login_required
def booking_list(request):
    """Liste aller Buchungen mit Filtern und Pagination"""
    # Get ContentType for Booking model to use in annotation
    booking_content_type = ContentType.objects.get_for_model(Booking)

    # Get all bookings with attachment count annotation
    # Using subquery to count attachments for each booking
    attachment_count_subquery = Attachment.objects.filter(
        content_type=booking_content_type,
        object_id=OuterRef('pk')
    ).values('object_id').annotate(count=Count('id')).values('count')

    bookings = Booking.objects.select_related('category', 'series').annotate(
        attachment_count=Subquery(attachment_count_subquery)
    )

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
                response['HX-Redirect'] = request.META.get('HTTP_REFERER', reverse('bookings:list'))
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
                # Add attachment count for the row
                booking_content_type = ContentType.objects.get_for_model(Booking)
                booking.attachment_count = Attachment.objects.filter(
                    content_type=booking_content_type,
                    object_id=booking.pk
                ).count()

                context = {
                    'booking': booking,
                    'today': date.today(),
                }
                response = render(request, 'bookings/_booking_row.html', context)
                # Trigger a page reload to refresh the list
                response['HX-Redirect'] = request.META.get('HTTP_REFERER', reverse('bookings:list'))
                return response

            return redirect('bookings:list')
    else:
        form = BookingForm(instance=booking)

    # Get attachments for this booking
    attachments = get_attachments_for(booking)

    context = {
        'form': form,
        'booking': booking,
        'attachments': attachments,
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

    # Add attachment count for the row
    booking_content_type = ContentType.objects.get_for_model(Booking)
    booking.attachment_count = Attachment.objects.filter(
        content_type=booking_content_type,
        object_id=booking.pk
    ).count()

    # Return updated row
    context = {
        'booking': booking,
        'today': date.today(),
    }
    return render(request, 'bookings/_booking_row.html', context)


@login_required
def booking_duplicate(request, booking_id):
    """Dupliziere eine Buchung mit heutigem Datum und Status 'planned'"""
    if request.method != 'POST':
        return HttpResponse(status=405)

    original = get_object_or_404(Booking, pk=booking_id)

    # Create duplicate with today's date and planned status
    new_booking = Booking.objects.create(
        date=date.today(),
        description=original.description,
        amount=original.amount,
        category=original.category,
        notes=original.notes,
        status='planned',
        series=None,  # Duplicate is always standalone
    )

    # Return edit form for the new booking
    form = BookingForm(instance=new_booking)
    context = {
        'form': form,
        'booking': new_booking,
        'is_duplicate': True,  # Flag to show "Verwerfen" button
    }

    # If HTMX request, return the form
    if request.htmx:
        return render(request, 'bookings/_booking_form.html', context)

    return render(request, 'bookings/booking_form.html', context)


@login_required
def quick_create(request):
    """
    Quick-entry form for creating bookings on the dashboard.
    GET: Returns the form (or button)
    POST: Saves booking and returns KPI cards for OOB swap
    """
    if request.method == 'POST':
        form = QuickBookingForm(request.POST)
        if form.is_valid():
            booking = form.save()

            # For HTMX requests, return updated KPI cards and success state
            if request.htmx:
                # Import here to avoid circular imports
                from dashboard.views import get_kpi_context

                # Get updated KPI data
                context = get_kpi_context()
                context['booking_created'] = True
                context['created_booking'] = booking

                # Return the quick entry form in success state (will reset to button)
                response = render(request, 'bookings/_quick_entry.html', context)
                # Trigger custom event for dashboard to listen to
                response['HX-Trigger'] = 'bookingCreated'
                return response

            messages.success(request, f'Buchung "{booking.description}" wurde erstellt.')
            return redirect('dashboard:index')
    else:
        form = QuickBookingForm()

    context = {'form': form}

    # If HTMX request, return the form partial
    if request.htmx:
        return render(request, 'bookings/_quick_entry.html', context)

    # Non-HTMX fallback: redirect to dashboard
    return redirect('dashboard:index')


@login_required
def receipt_upload(request):
    """
    Upload and analyze receipt/invoice for booking creation.
    GET: Returns upload form
    POST: Analyzes file and returns pre-filled booking form
    """
    if request.method == 'POST':
        # Check if file was uploaded
        if 'receipt_file' not in request.FILES:
            messages.error(request, 'Bitte wählen Sie eine Datei aus.')
            return render(request, 'bookings/_receipt_upload.html', {'error': 'Keine Datei ausgewählt'})

        uploaded_file = request.FILES['receipt_file']

        # Read file data
        file_data = uploaded_file.read()

        # Detect MIME type using python-magic
        mime_type = magic.from_buffer(file_data, mime=True)

        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf']
        if mime_type not in allowed_types:
            messages.error(request, f'Nicht unterstütztes Dateiformat: {mime_type}')
            return render(request, 'bookings/_receipt_upload.html', {
                'error': f'Nicht unterstütztes Dateiformat. Unterstützt: PDF, JPG, PNG, WEBP'
            })

        # Validate file size (10 MB)
        max_size = 10 * 1024 * 1024
        if len(file_data) > max_size:
            messages.error(request, 'Datei zu groß (max. 10 MB)')
            return render(request, 'bookings/_receipt_upload.html', {
                'error': 'Datei zu groß (max. 10 MB)'
            })

        try:
            # Call AI service to recognize receipt
            result = recognize_receipt(file_data, mime_type)

            # Store result and file data in session for later use
            request.session['receipt_result'] = {
                'date': result.date,
                'description': result.description,
                'amount': str(result.amount),
                'category_suggestion': result.category_suggestion,
                'notes': result.notes,
                'confidence': result.confidence,
                'raw_text': result.raw_text,
                'ai_provider': result.ai_provider,
                'ai_model': result.ai_model,
            }

            # Store file data in session (base64 encoded for JSON serialization)
            import base64
            request.session['receipt_file_data'] = base64.b64encode(file_data).decode('utf-8')
            request.session['receipt_file_name'] = uploaded_file.name
            request.session['receipt_file_mime_type'] = mime_type

            # Pre-fill form with recognized data
            initial_data = {
                'date': result.date if result.date else date.today(),
                'description': result.description,
                'amount': result.amount,
                'status': 'planned',  # Default to planned for review
                'notes': result.notes,
            }

            # Try to find matching category by name
            try:
                category = Category.objects.get(name__iexact=result.category_suggestion)
                initial_data['category'] = category
            except Category.DoesNotExist:
                # Category not found, user will need to select
                pass

            form = BookingForm(initial=initial_data)

            context = {
                'form': form,
                'receipt_result': result,
                'is_receipt_form': True,
            }

            return render(request, 'bookings/_receipt_form.html', context)

        except AIProviderNotConfigured as e:
            messages.error(request, 'KI nicht konfiguriert — bitte API-Key in den Einstellungen hinterlegen')
            return render(request, 'bookings/_receipt_upload.html', {
                'error': 'KI nicht konfiguriert — bitte API-Key in den Einstellungen hinterlegen'
            })

        except AIServiceError as e:
            messages.error(request, f'KI-Fehler: {str(e)}')
            return render(request, 'bookings/_receipt_upload.html', {
                'error': f'KI-Analyse fehlgeschlagen: {str(e)}'
            })

        except AIResponseParseError as e:
            messages.error(request, f'Fehler beim Verarbeiten der KI-Antwort: {str(e)}')
            return render(request, 'bookings/_receipt_upload.html', {
                'error': f'Ungültige KI-Antwort. Bitte versuchen Sie es erneut.'
            })

        except ValueError as e:
            # PDF conversion error
            messages.error(request, f'Fehler beim Verarbeiten der Datei: {str(e)}')
            return render(request, 'bookings/_receipt_upload.html', {
                'error': f'Fehler beim Verarbeiten der Datei: {str(e)}'
            })

        except Exception as e:
            messages.error(request, f'Unerwarteter Fehler: {str(e)}')
            return render(request, 'bookings/_receipt_upload.html', {
                'error': f'Unerwarteter Fehler: {str(e)}'
            })

    # GET request: show upload form
    return render(request, 'bookings/_receipt_upload.html')


@login_required
def receipt_confirm(request):
    """
    Confirm and save booking from receipt recognition.
    Creates booking and attaches the receipt file.
    """
    if request.method != 'POST':
        return HttpResponse(status=405)

    # Check if we have session data
    if 'receipt_result' not in request.session or 'receipt_file_data' not in request.session:
        messages.error(request, 'Keine Beleg-Daten gefunden. Bitte laden Sie den Beleg erneut hoch.')
        return render(request, 'bookings/_receipt_upload.html', {
            'error': 'Session abgelaufen. Bitte laden Sie den Beleg erneut hoch.'
        })

    # Validate form
    form = BookingForm(request.POST)
    if not form.is_valid():
        # Return form with errors
        receipt_result_data = request.session.get('receipt_result')
        context = {
            'form': form,
            'receipt_result': type('obj', (object,), receipt_result_data)(),  # Convert dict to object
            'is_receipt_form': True,
        }
        return render(request, 'bookings/_receipt_form.html', context)

    # Create booking
    booking = form.save()

    # Create attachment from stored file data
    try:
        import base64
        file_data = base64.b64decode(request.session['receipt_file_data'])
        file_name = request.session['receipt_file_name']
        mime_type = request.session['receipt_file_mime_type']

        # Create attachment using handle_upload service
        from django.core.files.uploadedfile import InMemoryUploadedFile
        from io import BytesIO

        file_obj = InMemoryUploadedFile(
            file=BytesIO(file_data),
            field_name='file',
            name=file_name,
            content_type=mime_type,
            size=len(file_data),
            charset=None
        )

        attachment = handle_upload(
            uploaded_file=file_obj,
            content_object=booking
        )

    except Exception as e:
        # Log error but don't fail the booking creation
        messages.warning(request, f'Buchung erstellt, aber Anhang konnte nicht gespeichert werden: {str(e)}')

    # Clear session data
    del request.session['receipt_result']
    del request.session['receipt_file_data']
    del request.session['receipt_file_name']
    del request.session['receipt_file_mime_type']

    messages.success(request, f'Buchung "{booking.description}" aus Beleg erstellt.')

    # For HTMX: redirect to booking list
    if request.htmx:
        response = HttpResponse('')
        response['HX-Redirect'] = reverse('bookings:list')
        return response

    return redirect('bookings:list')


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
            return redirect('category_list')
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
            return redirect('category_list')
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
        return redirect('category_list')

    category_name = category.name
    category.delete()

    # If HTMX request, return empty response (row will be removed)
    if request.htmx:
        return HttpResponse('')

    messages.success(request, f'Kategorie "{category_name}" wurde gelöscht.')
    return redirect('category_list')


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

    # Get planned carry forward (all bookings, booked + planned, before this month)
    planned_carry_forward = get_planned_carry_forward(year, month)

    # Get previous month cumulative values
    prev_month_cumulative_result = get_previous_month_cumulative_result(year, month)
    prev_month_end_balance = get_previous_month_end_balance(year, month)

    # Get all bookings for this month
    # Add attachment count annotation using the same pattern as booking_list
    booking_content_type = ContentType.objects.get_for_model(Booking)
    attachment_count_subquery = Attachment.objects.filter(
        content_type=booking_content_type,
        object_id=OuterRef('pk')
    ).values('object_id').annotate(count=Count('id')).values('count')

    bookings = get_bookings_for_month(year, month).select_related('category', 'series').annotate(
        attachment_count=Subquery(attachment_count_subquery)
    )

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
        'planned_carry_forward': planned_carry_forward,
        'month_income': month_income,
        'month_expenses': month_expenses,
        'month_result': month_result,
        'prev_month_cumulative_result': prev_month_cumulative_result,
        'end_balance': end_balance,
        'prev_month_end_balance': prev_month_end_balance,
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
