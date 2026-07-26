from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.utils.http import urlencode
from django.db.models import Q, Count, Subquery, OuterRef
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from datetime import date, datetime, timedelta
from calendar import monthrange
from decimal import Decimal, InvalidOperation
import magic
from .models import Booking, Category, RecurringSeries, Liability, Asset, ReconciliationLog
from .forms import BookingForm, BookingFilterForm, MonthFilterForm, RecurringSeriesForm, SeriesAmountChangeForm, SeriesExtendForm, CategoryForm, QuickBookingForm, LiabilityForm, AssetForm, AssetQuickUpdateForm, ReconciliationForm
from .services import (
    get_monthly_carry_forward,
    get_bookings_for_month,
    get_planned_carry_forward,
    get_previous_month_cumulative_result,
    get_previous_month_end_balance,
    get_total_liabilities,
    get_liabilities_overview,
    get_total_assets,
    get_net_worth,
    get_assets_by_category,
    get_category_overview,
    get_category_bookings,
    get_current_balance,
)
from .wizard import preview_series_bookings, create_series_bookings
from .receipt_service import recognize_receipt, ReceiptRecognitionResult
from attachments.services import get_attachments_for, handle_upload
from attachments.models import Attachment
from ai.exceptions import AIProviderNotConfigured, AIServiceError, AIResponseParseError

MONTH_NAMES = [
    'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
    'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'
]


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


def _get_return_month_context(request):
    """
    Extract the optional month-view origin (year/month) a receipt upload was
    started from, so the caller can return there / detect a cross-month booking.
    Present as GET params when the modal is opened from month_view, and
    resubmitted as hidden POST fields through the upload/confirm steps.
    """
    return_year = request.POST.get('return_year') or request.GET.get('return_year')
    return_month = request.POST.get('return_month') or request.GET.get('return_month')
    try:
        return_year = int(return_year)
        return_month = int(return_month)
        if not (1 <= return_month <= 12):
            raise ValueError
    except (TypeError, ValueError):
        return {'return_year': None, 'return_month': None}
    return {'return_year': return_year, 'return_month': return_month}


@login_required
def receipt_upload(request):
    """
    Upload and analyze receipt/invoice for booking creation.
    GET: Returns upload form
    POST: Analyzes file and returns pre-filled booking form
    """
    month_context = _get_return_month_context(request)

    if request.method == 'POST':
        # Check if file was uploaded
        if 'receipt_file' not in request.FILES:
            messages.error(request, 'Bitte wählen Sie eine Datei aus.')
            return render(request, 'bookings/_receipt_upload.html', {'error': 'Keine Datei ausgewählt', **month_context})

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
                'error': f'Nicht unterstütztes Dateiformat. Unterstützt: PDF, JPG, PNG, WEBP',
                **month_context,
            })

        # Validate file size (10 MB)
        max_size = 10 * 1024 * 1024
        if len(file_data) > max_size:
            messages.error(request, 'Datei zu groß (max. 10 MB)')
            return render(request, 'bookings/_receipt_upload.html', {
                'error': 'Datei zu groß (max. 10 MB)',
                **month_context,
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
                **month_context,
            }

            return render(request, 'bookings/_receipt_form.html', context)

        except AIProviderNotConfigured as e:
            messages.error(request, 'KI nicht konfiguriert — bitte API-Key in den Einstellungen hinterlegen')
            return render(request, 'bookings/_receipt_upload.html', {
                'error': 'KI nicht konfiguriert — bitte API-Key in den Einstellungen hinterlegen',
                **month_context,
            })

        except AIServiceError as e:
            messages.error(request, f'KI-Fehler: {str(e)}')
            return render(request, 'bookings/_receipt_upload.html', {
                'error': f'KI-Analyse fehlgeschlagen: {str(e)}',
                **month_context,
            })

        except AIResponseParseError as e:
            messages.error(request, f'Fehler beim Verarbeiten der KI-Antwort: {str(e)}')
            return render(request, 'bookings/_receipt_upload.html', {
                'error': f'Ungültige KI-Antwort. Bitte versuchen Sie es erneut.',
                **month_context,
            })

        except ValueError as e:
            # PDF conversion error
            messages.error(request, f'Fehler beim Verarbeiten der Datei: {str(e)}')
            return render(request, 'bookings/_receipt_upload.html', {
                'error': f'Fehler beim Verarbeiten der Datei: {str(e)}',
                **month_context,
            })

        except Exception as e:
            messages.error(request, f'Unerwarteter Fehler: {str(e)}')
            return render(request, 'bookings/_receipt_upload.html', {
                'error': f'Unerwarteter Fehler: {str(e)}',
                **month_context,
            })

    # GET request: show upload form
    return render(request, 'bookings/_receipt_upload.html', month_context)


@login_required
def receipt_confirm(request):
    """
    Confirm and save booking from receipt recognition.
    Creates booking and attaches the receipt file.
    """
    if request.method != 'POST':
        return HttpResponse(status=405)

    month_context = _get_return_month_context(request)

    # Check if we have session data
    if 'receipt_result' not in request.session or 'receipt_file_data' not in request.session:
        messages.error(request, 'Keine Beleg-Daten gefunden. Bitte laden Sie den Beleg erneut hoch.')
        return render(request, 'bookings/_receipt_upload.html', {
            'error': 'Session abgelaufen. Bitte laden Sie den Beleg erneut hoch.',
            **month_context,
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
            **month_context,
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
            file=file_obj,
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

    # Opened from the month view: report back into the modal instead of
    # navigating away, since the booking may belong to a different month
    # than the one currently displayed (and would otherwise look "lost").
    if request.htmx and month_context['return_year'] and month_context['return_month']:
        return_year = month_context['return_year']
        return_month = month_context['return_month']
        same_month = booking.date.year == return_year and booking.date.month == return_month
        response = render(request, 'bookings/_receipt_success.html', {
            'booking': booking,
            'same_month': same_month,
            'return_year': return_year,
            'return_month': return_month,
            'booking_month_label': f"{MONTH_NAMES[booking.date.month - 1]} {booking.date.year}",
        })
        if same_month:
            # Let month_view.html reload #month-content and close the modal
            response['HX-Trigger'] = 'receiptBookingSaved'
        return response

    # For HTMX: redirect to booking list
    if request.htmx:
        response = HttpResponse('')
        response['HX-Redirect'] = reverse('bookings:list')
        return response

    return redirect('bookings:list')


# Display metadata for the category overview groups (order matters).
_CATEGORY_OVERVIEW_GROUPS = [
    ('income', 'Einnahmen', 'bi-arrow-down-circle', 'bg-success', False, None),
    ('expense', 'Ausgaben', 'bi-arrow-up-circle', 'bg-danger', False, None),
    ('neutral', 'Neutral', 'bi-arrow-left-right', 'bg-secondary', True,
     'Durchlaufende Posten und Umbuchungen — nicht in Statistiken enthalten (is_statistical=False).'),
]


def _parse_overview_period(request):
    """
    Resolve the requested reporting period and status from request GET params.

    Returns:
        tuple: (start_date, end_date, include_planned, period, status)
        where period in {'month', 'year', 'custom'} and status in {'booked', 'all'}.
    """
    today = date.today()
    period = request.GET.get('period', 'month')
    status = request.GET.get('status', 'booked')
    include_planned = status == 'all'

    def _parse(value):
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    if period == 'year':
        start = date(today.year, 1, 1)
        end = date(today.year, 12, 31)
    elif period == 'custom':
        start = _parse(request.GET.get('start'))
        end = _parse(request.GET.get('end'))
        # Fall back to the current month for missing/invalid custom bounds.
        if start is None:
            start = date(today.year, today.month, 1)
        if end is None:
            end = date(today.year, today.month, monthrange(today.year, today.month)[1])
        # Guard against a reversed range.
        if end < start:
            start, end = end, start
    else:
        period = 'month'
        start = date(today.year, today.month, 1)
        end = date(today.year, today.month, monthrange(today.year, today.month)[1])

    return start, end, include_planned, period, status


@login_required
def category_overview(request):
    """
    Übersicht aller Kategorien mit ihrer Summe im gewählten Zeitraum,
    gruppiert nach Typ. Drilldown auf einzelne Buchungen per HTMX.
    """
    start, end, include_planned, period, status = _parse_overview_period(request)
    grouped = get_category_overview(start, end, include_planned)

    groups = []
    for key, label, icon, badge_class, is_neutral, hint in _CATEGORY_OVERVIEW_GROUPS:
        data = grouped[key]
        groups.append({
            'key': key,
            'label': label,
            'icon': icon,
            'badge_class': badge_class,
            'is_neutral': is_neutral,
            'hint': hint,
            'categories': data['categories'],
            'total': data['total'],
        })

    income_total = grouped['income']['total']
    expense_total = grouped['expense']['total']

    # Query string used by the drilldown links so they filter the same period.
    drilldown_query = urlencode({
        'start': start.isoformat(),
        'end': end.isoformat(),
        'status': status,
    })

    context = {
        'groups': groups,
        'income_total': income_total,
        'expense_total': expense_total,
        'net_total': income_total + expense_total,
        'period': period,
        'status': status,
        'start': start,
        'end': end,
        'drilldown_query': drilldown_query,
    }

    if request.htmx:
        return render(request, 'bookings/_category_overview_content.html', context)

    return render(request, 'bookings/category_overview.html', context)


@login_required
def category_overview_bookings(request, category_id):
    """Drilldown: Buchungen einer Kategorie im gewählten Zeitraum (HTMX-Partial)."""
    category = get_object_or_404(Category, pk=category_id)
    start, end, include_planned, period, status = _parse_overview_period(request)
    bookings = get_category_bookings(category, start, end, include_planned)

    context = {
        'category': category,
        'bookings': bookings,
    }
    return render(request, 'bookings/_category_overview_bookings.html', context)


@login_required
def category_list(request):
    """Liste aller Kategorien mit Buchungsanzahl, gruppiert nach Typ"""
    categories = Category.objects.annotate(
        booking_count=Count('bookings')
    ).order_by('category_type', 'name')

    context = {
        'income_categories': categories.filter(category_type='income'),
        'expense_categories': categories.filter(category_type='expense'),
        'neutral_categories': categories.filter(category_type='neutral'),
        'total_categories': categories.count(),
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
    show_archived = request.GET.get('archived') == '1'
    series = RecurringSeries.objects.select_related('category').filter(
        archived=show_archived
    ).order_by('-created_at')

    series_content_type = ContentType.objects.get_for_model(RecurringSeries)

    # Annotate with booking count, planned (not yet booked) count and attachment count
    series_with_counts = []
    for s in series:
        series_with_counts.append({
            'series': s,
            'booking_count': s.bookings.count(),
            'planned_count': s.bookings.filter(status='planned').count(),
            'attachment_count': Attachment.objects.filter(
                content_type=series_content_type,
                object_id=s.pk
            ).count(),
        })

    context = {
        'series_with_counts': series_with_counts,
        'show_archived': show_archived,
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

    if request.htmx:
        return HttpResponse('')

    # Add success message
    messages.success(
        request,
        f'Serie "{series_description}" und {booking_count} verknüpfte Buchungen wurden gelöscht.'
    )

    return redirect('bookings:series_list')


@login_required
def series_archive(request, series_id):
    """Archiviere eine Serie: keine neuen Buchungen mehr, geplante (nicht gebuchte)
    Buchungen werden entfernt, gebuchte Buchungen bleiben als Historie erhalten."""
    if request.method != 'POST':
        return HttpResponse(status=405)

    series = get_object_or_404(RecurringSeries, pk=series_id)

    deleted_count, _ = series.bookings.filter(status='planned').delete()
    series.archived = True
    series.save(update_fields=['archived'])

    if request.htmx:
        return HttpResponse('')

    messages.success(
        request,
        f'Serie "{series.description}" wurde archiviert. '
        f'{deleted_count} geplante Buchung(en) wurden entfernt, gebuchte Buchungen bleiben erhalten.'
    )
    return redirect('bookings:series_list')


@login_required
def series_restore(request, series_id):
    """Hole eine archivierte Serie zurück in die Standardliste (ohne neue Buchungen zu erzeugen)."""
    if request.method != 'POST':
        return HttpResponse(status=405)

    series = get_object_or_404(RecurringSeries, pk=series_id)

    series.archived = False
    series.save(update_fields=['archived'])

    if request.htmx:
        return HttpResponse('')

    messages.success(request, f'Serie "{series.description}" wurde wiederhergestellt.')
    return redirect('bookings:series_list')


@login_required
def series_amount_change(request, series_id):
    """Ändere den Betrag einer Serie ab einem Stichtag (nur künftige, ungebuchte Buchungen)"""
    series = get_object_or_404(RecurringSeries, pk=series_id)

    if request.method == 'POST':
        form = SeriesAmountChangeForm(request.POST)
        if form.is_valid():
            new_amount = form.cleaned_data['new_amount']
            valid_from = form.cleaned_data['valid_from']

            updated_count = Booking.objects.filter(
                series=series,
                status='planned',
                date__gte=valid_from,
            ).update(amount=new_amount)

            series.amount = new_amount
            series.save(update_fields=['amount'])

            if request.htmx:
                response = HttpResponse('')
                response['HX-Redirect'] = reverse('bookings:series_list')
                return response

            messages.success(
                request,
                f'Betrag der Serie "{series.description}" wurde angepasst. '
                f'{updated_count} geplante Buchung(en) ab {valid_from.strftime("%d.%m.%Y")} wurden aktualisiert.'
            )
            return redirect('bookings:series_list')
    else:
        form = SeriesAmountChangeForm(initial={
            'new_amount': series.amount,
            'valid_from': date.today(),
        })

    context = {
        'form': form,
        'series': series,
    }

    if request.htmx:
        return render(request, 'bookings/_series_amount_form.html', context)

    return render(request, 'bookings/series_amount_form.html', context)


@login_required
def series_extend(request, series_id):
    """Verlängere eine Serie bis zu einem Zieldatum und lege fehlende Buchungen bis dahin an"""
    series = get_object_or_404(RecurringSeries, pk=series_id)

    if series.archived:
        if request.htmx:
            return HttpResponse(status=400)
        messages.error(
            request,
            f'Serie "{series.description}" ist archiviert und kann nicht verlängert werden.'
        )
        return redirect('bookings:series_list')

    if request.method == 'POST':
        form = SeriesExtendForm(request.POST, series=series)
        if form.is_valid():
            target_end_date = form.cleaned_data['new_end_date']

            max_end_date = series.start_date + timedelta(days=3650)
            capped = target_end_date > max_end_date
            if capped:
                target_end_date = max_end_date

            series.end_date = target_end_date
            series.save(update_fields=['end_date'])

            created_bookings = create_series_bookings(series)

            if request.htmx:
                response = HttpResponse('')
                response['HX-Redirect'] = reverse('bookings:series_list')
                return response

            message = (
                f'Serie "{series.description}" wurde bis {target_end_date.strftime("%d.%m.%Y")} verlängert. '
                f'{len(created_bookings)} neue Buchung(en) wurden angelegt.'
            )
            if capped:
                message += ' Das Zieldatum wurde auf maximal 10 Jahre ab Serienstart begrenzt.'
            messages.success(request, message)
            return redirect('bookings:series_list')
    else:
        form = SeriesExtendForm(series=series, initial={
            'new_end_date': series.end_date or date.today(),
        })

    context = {
        'form': form,
        'series': series,
    }

    if request.htmx:
        return render(request, 'bookings/_series_extend_form.html', context)

    return render(request, 'bookings/series_extend_form.html', context)


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
    # These are always based on the full, unfiltered month so that the
    # cumulative balance per row and the summary bar stay correct even
    # when the filter below hides some rows.
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

    # Apply row filters (date/amount/category/description) on top of the
    # already-computed running balances. This only narrows which rows are
    # displayed - it never changes the running balance or the summary bar.
    filter_form = MonthFilterForm(
        request.GET,
        month_url=reverse('bookings:month_view_detail', args=[year, month])
    )
    is_filtered = False
    if filter_form.is_valid():
        date_from = filter_form.cleaned_data.get('date_from')
        date_to = filter_form.cleaned_data.get('date_to')
        amount_min = filter_form.cleaned_data.get('amount_min')
        amount_max = filter_form.cleaned_data.get('amount_max')
        booking_type = filter_form.cleaned_data.get('type')
        category_filter = filter_form.cleaned_data.get('category')
        description_filter = filter_form.cleaned_data.get('description')

        is_filtered = any([
            date_from, date_to, amount_min is not None, amount_max is not None,
            booking_type, category_filter, description_filter,
        ])

        def matches_filter(booking):
            if date_from and booking.date < date_from:
                return False
            if date_to and booking.date > date_to:
                return False
            if amount_min is not None and booking.amount < amount_min:
                return False
            if amount_max is not None and booking.amount > amount_max:
                return False
            if booking_type == 'income' and booking.amount < 0:
                return False
            if booking_type == 'expense' and booking.amount >= 0:
                return False
            if category_filter and booking.category_id != category_filter.id:
                return False
            if description_filter and description_filter.lower() not in booking.description.lower():
                return False
            return True

        filtered_bookings_with_balance = [
            item for item in bookings_with_balance if matches_filter(item['booking'])
        ]
    else:
        filtered_bookings_with_balance = bookings_with_balance

    # Sum of the currently visible (filtered) rows, shown separately from
    # the month summary bar which always reflects the full month.
    filtered_income = Decimal('0.00')
    filtered_expenses = Decimal('0.00')
    for item in filtered_bookings_with_balance:
        if item['booking'].amount >= 0:
            filtered_income += item['booking'].amount
        else:
            filtered_expenses += item['booking'].amount
    filtered_result = filtered_income + filtered_expenses

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

    month_label = f"{MONTH_NAMES[month - 1]} {year}"

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
        'bookings_with_balance': filtered_bookings_with_balance,
        'total_booking_count': len(bookings_with_balance),
        'filter_form': filter_form,
        'is_filtered': is_filtered,
        'filtered_income': filtered_income,
        'filtered_expenses': filtered_expenses,
        'filtered_result': filtered_result,
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


# =========================
# Liability Views
# =========================

@login_required
def liability_list(request):
    """Liste aller Verbindlichkeiten mit Übersicht"""
    liabilities_overview = get_liabilities_overview()
    total_outstanding = get_total_liabilities()

    # Count open liabilities
    open_count = sum(1 for item in liabilities_overview if not item['is_closed'])

    # Sort: open first, then closed (dimmed)
    liabilities_overview.sort(key=lambda x: (x['is_closed'], -x['liability'].created_at.timestamp()))

    context = {
        'liabilities_overview': liabilities_overview,
        'total_outstanding': total_outstanding,
        'open_count': open_count,
    }

    # If HTMX request, return only the list partial
    if request.htmx:
        return render(request, 'bookings/_liability_list.html', context)

    return render(request, 'bookings/liability_list.html', context)


@login_required
def liability_create(request):
    """Erstelle eine neue Verbindlichkeit"""
    if request.method == 'POST':
        form = LiabilityForm(request.POST)
        if form.is_valid():
            liability = form.save()

            # If HTMX request, redirect to list
            if request.htmx:
                response = HttpResponse('')
                response['HX-Redirect'] = reverse('bookings:liability_list')
                return response

            messages.success(request, f'Verbindlichkeit "{liability.name}" wurde erstellt.')
            return redirect('bookings:liability_list')
    else:
        form = LiabilityForm()

    context = {'form': form}

    # If HTMX request, return only the form
    if request.htmx:
        return render(request, 'bookings/_liability_form.html', context)

    return render(request, 'bookings/liability_form.html', context)


@login_required
def liability_detail(request, liability_id):
    """Detailansicht einer Verbindlichkeit"""
    liability = get_object_or_404(Liability, pk=liability_id)

    # Get all linked bookings
    linked_bookings = liability.bookings.filter(amount__lt=0).select_related('category').order_by('-date')

    context = {
        'liability': liability,
        'linked_bookings': linked_bookings,
        'total_repaid': liability.total_repaid,
        'remaining': liability.remaining,
        'repaid_percent': liability.repaid_percent,
        'is_closed': liability.is_closed,
    }

    return render(request, 'bookings/liability_detail.html', context)


@login_required
def liability_edit(request, liability_id):
    """Bearbeite eine Verbindlichkeit"""
    liability = get_object_or_404(Liability, pk=liability_id)

    if request.method == 'POST':
        form = LiabilityForm(request.POST, instance=liability)
        if form.is_valid():
            liability = form.save()

            # If HTMX request, redirect to detail or list
            if request.htmx:
                response = HttpResponse('')
                response['HX-Redirect'] = reverse('bookings:liability_detail', args=[liability.id])
                return response

            messages.success(request, f'Verbindlichkeit "{liability.name}" wurde aktualisiert.')
            return redirect('bookings:liability_detail', liability_id=liability.id)
    else:
        form = LiabilityForm(instance=liability)

    context = {
        'form': form,
        'liability': liability,
    }

    # If HTMX request, return only the form
    if request.htmx:
        return render(request, 'bookings/_liability_form.html', context)

    return render(request, 'bookings/liability_form.html', context)


@login_required
def liability_delete(request, liability_id):
    """Lösche eine Verbindlichkeit"""
    if request.method != 'POST':
        return HttpResponse(status=405)

    liability = get_object_or_404(Liability, pk=liability_id)

    # Count linked bookings
    booking_count = liability.bookings.count()
    liability_name = liability.name

    # Delete the liability (linked bookings will have liability set to NULL)
    liability.delete()

    # If HTMX request, return empty response
    if request.htmx:
        return HttpResponse('')

    messages.success(
        request,
        f'Verbindlichkeit "{liability_name}" wurde gelöscht. '
        f'{booking_count} Buchung{"en" if booking_count != 1 else ""} wurde{"n" if booking_count != 1 else ""} von der Verbindlichkeit getrennt.'
    )

    return redirect('bookings:liability_list')


# ============================================================================
# ASSET VIEWS
# ============================================================================

@login_required
def asset_list(request):
    """Liste aller Vermögensgegenstände mit Übersicht"""
    assets = Asset.objects.all()
    total_assets = get_total_assets()
    total_liabilities = get_total_liabilities()
    net_worth = get_net_worth()
    assets_by_category = get_assets_by_category()

    context = {
        'assets': assets,
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'net_worth': net_worth,
        'assets_by_category': assets_by_category,
    }

    # If HTMX request, return only the list partial
    if request.htmx:
        return render(request, 'bookings/_asset_list.html', context)

    return render(request, 'bookings/asset_list.html', context)


@login_required
def asset_create(request):
    """Erstelle einen neuen Vermögensgegenstand"""
    if request.method == 'POST':
        form = AssetForm(request.POST)
        if form.is_valid():
            asset = form.save()

            # If HTMX request, redirect to list
            if request.htmx:
                response = HttpResponse('')
                response['HX-Redirect'] = reverse('bookings:asset_list')
                return response

            messages.success(request, f'Vermögensgegenstand "{asset.name}" wurde erstellt.')
            return redirect('bookings:asset_list')
    else:
        form = AssetForm()

    context = {'form': form}

    # If HTMX request, return only the form
    if request.htmx:
        return render(request, 'bookings/_asset_form.html', context)

    return render(request, 'bookings/asset_form.html', context)


@login_required
def asset_edit(request, asset_id):
    """Bearbeite einen Vermögensgegenstand"""
    asset = get_object_or_404(Asset, pk=asset_id)

    if request.method == 'POST':
        form = AssetForm(request.POST, instance=asset)
        if form.is_valid():
            asset = form.save()

            # If HTMX request, redirect to list
            if request.htmx:
                response = HttpResponse('')
                response['HX-Redirect'] = reverse('bookings:asset_list')
                return response

            messages.success(request, f'Vermögensgegenstand "{asset.name}" wurde aktualisiert.')
            return redirect('bookings:asset_list')
    else:
        form = AssetForm(instance=asset)

    context = {
        'form': form,
        'asset': asset,
    }

    # If HTMX request, return only the form
    if request.htmx:
        return render(request, 'bookings/_asset_form.html', context)

    return render(request, 'bookings/asset_form.html', context)


@login_required
def asset_delete(request, asset_id):
    """Lösche einen Vermögensgegenstand"""
    if request.method != 'POST':
        return HttpResponse(status=405)

    asset = get_object_or_404(Asset, pk=asset_id)
    asset_name = asset.name
    asset.delete()

    # If HTMX request, return empty response
    if request.htmx:
        return HttpResponse('')

    messages.success(
        request,
        f'Vermögensgegenstand "{asset_name}" wurde gelöscht.'
    )

    return redirect('bookings:asset_list')


@login_required
def asset_update_value(request, asset_id):
    """Schnell-Update für aktuellen Wert eines Vermögensgegenstands (HTMX)"""
    if request.method != 'POST':
        return HttpResponse(status=405)

    asset = get_object_or_404(Asset, pk=asset_id)
    form = AssetQuickUpdateForm(request.POST, instance=asset)

    if form.is_valid():
        asset = form.save()
        # Return updated row partial
        context = {'asset': asset}
        return render(request, 'bookings/_asset_row.html', context)
    else:
        # Return error or re-render the row with the edit form
        context = {
            'asset': asset,
            'edit_mode': True,
            'form': form,
        }
        return render(request, 'bookings/_asset_row.html', context)


def _parse_decimal(raw):
    """Best-effort parse of a decimal from a query/form value (accepts comma as separator)."""
    if not raw:
        return None
    try:
        return Decimal(raw.strip().replace(',', '.'))
    except InvalidOperation:
        return None


def _reconciliation_context(form, expected_balance, actual_balance):
    difference = (actual_balance - expected_balance) if actual_balance is not None else None
    return {
        'form': form,
        'expected_balance': expected_balance,
        'actual_balance': actual_balance,
        'difference': difference,
        'logs': ReconciliationLog.objects.select_related('booking')[:12],
    }


@login_required
def reconciliation_view(request):
    """Kontenabgleich: Ist-Gesamtstand gegen das MoneyPlan-Soll prüfen und Differenz anzeigen."""
    expected_balance = get_current_balance()
    actual_balance = _parse_decimal(request.GET.get('actual_balance'))

    default_category = Category.objects.filter(category_type='neutral').first()
    category_id = request.GET.get('category') or (default_category.pk if default_category else None)

    form = ReconciliationForm(
        initial={'actual_balance': actual_balance, 'category': category_id},
        calc_url=reverse('bookings:reconciliation'),
    )

    context = _reconciliation_context(form, expected_balance, actual_balance)

    if request.htmx:
        return render(request, 'bookings/_reconciliation_result.html', context)

    return render(request, 'bookings/reconciliation.html', context)


@login_required
def reconciliation_create(request):
    """Erstellt die Ausgleichsbuchung (gebucht, heutiges Datum, Differenzbetrag, neutrale Kategorie) und protokolliert den Abgleich."""
    if request.method != 'POST':
        return HttpResponse(status=405)

    expected_balance = get_current_balance()
    form = ReconciliationForm(request.POST, calc_url=reverse('bookings:reconciliation'))

    if form.is_valid():
        actual_balance = form.cleaned_data['actual_balance']
        category = form.cleaned_data['category']
        difference = actual_balance - expected_balance

        booking = None
        if difference != 0:
            booking = Booking.objects.create(
                date=date.today(),
                description='Kontenabgleich',
                amount=difference,
                category=category,
                status='booked',
                notes=f'Ist-Gesamtstand: {actual_balance:.2f} € / MoneyPlan-Soll: {expected_balance:.2f} €',
            )

        ReconciliationLog.objects.create(
            actual_balance=actual_balance,
            expected_balance=expected_balance,
            difference=difference,
            booking=booking,
        )

        if request.htmx:
            response = HttpResponse('')
            response['HX-Redirect'] = reverse('bookings:reconciliation')
            return response

        if difference == 0:
            messages.success(request, 'Ist-Gesamtstand stimmt mit dem MoneyPlan-Saldo überein — keine Ausgleichsbuchung nötig.')
        else:
            messages.success(request, f'Ausgleichsbuchung über {difference:+.2f} € wurde erstellt.')

        return redirect('bookings:reconciliation')

    actual_balance = form.data.get('actual_balance') and _parse_decimal(form.data.get('actual_balance'))
    context = _reconciliation_context(form, expected_balance, actual_balance)

    if request.htmx:
        return render(request, 'bookings/_reconciliation_result.html', context)

    return render(request, 'bookings/reconciliation.html', context)


