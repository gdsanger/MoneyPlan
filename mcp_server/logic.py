"""
Plain synchronous business logic behind the MCP tools.

Each function validates its inputs, calls the existing models/services, and
returns JSON-serializable data. Kept free of any MCP/async concerns so it can
be unit-tested directly and reused by the thin async tool wrappers in
`mcp_server.server`. Validation errors are raised as `ValueError` with a
message written for an AI agent to read and act on.
"""
import base64
import binascii
from datetime import date as date_type, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Count

from alerts.models import AlertConfig
from attachments.models import Attachment
from attachments.services import delete_attachment as delete_attachment_service
from attachments.services import get_attachments_for, handle_upload
from bookings.models import Booking, Category, Liability, RecurringSeries
from bookings.wizard import create_series_bookings
from timetracking.models import Client, TimeEntry

from .resolvers import resolve_category, resolve_client
from .serializers import serialize_attachment, serialize_booking, serialize_series, serialize_time_entry

TWO_PLACES = Decimal('0.01')

# Independent from settings.MAX_UPLOAD_SIZE_MB (10 MB): rejects oversized Base64
# payloads before they reach handle_upload's own size/MIME validation, since
# invoice/receipt attachments are expected to be well under 100 KB.
MCP_MAX_ATTACHMENT_SIZE_MB = 2


def _parse_date(value, field_name='date'):
    if isinstance(value, date_type):
        return value
    if isinstance(value, str):
        try:
            return date_type.fromisoformat(value.strip())
        except ValueError:
            raise ValueError(
                f"Ungültiges Datum für '{field_name}': '{value}'. Erwartet wird das Format YYYY-MM-DD."
            )
    raise ValueError(f"Ungültiges Datum für '{field_name}': {value!r}")


def _parse_amount(value, field_name='amount'):
    try:
        return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError):
        raise ValueError(f"Ungültiger Betrag für '{field_name}': {value!r}")


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------

def create_booking(date, description, amount, category, status='planned',
                    notes='', series_id=None, liability_id=None):
    booking_date = _parse_date(date)

    description = (description or '').strip()
    if not description:
        raise ValueError("Beschreibung darf nicht leer sein.")

    amount_dec = _parse_amount(amount)
    if amount_dec == 0:
        raise ValueError("Betrag darf nicht 0 sein (positiv = Einnahme, negativ = Ausgabe).")

    valid_statuses = dict(Booking.STATUS_CHOICES)
    if status not in valid_statuses:
        raise ValueError(f"Ungültiger Status '{status}'. Erlaubt: {', '.join(valid_statuses)}.")

    category_obj = resolve_category(category)

    series = None
    if series_id is not None:
        try:
            series = RecurringSeries.objects.get(pk=series_id)
        except RecurringSeries.DoesNotExist:
            raise ValueError(f"Serie mit ID {series_id} nicht gefunden.")

    liability = None
    if liability_id is not None:
        try:
            liability = Liability.objects.get(pk=liability_id)
        except Liability.DoesNotExist:
            raise ValueError(f"Verbindlichkeit mit ID {liability_id} nicht gefunden.")

    booking = Booking.objects.create(
        date=booking_date,
        description=description,
        amount=amount_dec,
        status=status,
        category=category_obj,
        series=series,
        liability=liability,
        notes=notes or '',
    )
    return serialize_booking(booking)


def _with_attachment_counts(items):
    """Adds 'attachment_count' to each serialized booking dict via a single
    grouped query, so callers can see whether a receipt is already attached
    without an extra list_booking_attachments round-trip per booking."""
    if not items:
        return items
    booking_ct = ContentType.objects.get_for_model(Booking)
    ids = [item['id'] for item in items]
    counts = {
        row['object_id']: row['count']
        for row in Attachment.objects.filter(content_type=booking_ct, object_id__in=ids)
        .values('object_id')
        .annotate(count=Count('id'))
    }
    for item in items:
        item['attachment_count'] = counts.get(item['id'], 0)
    return items


def list_planned_bookings(date_from=None, date_to=None, category=None, limit=None):
    qs = Booking.objects.filter(status='planned')
    if date_from is not None:
        qs = qs.filter(date__gte=_parse_date(date_from, 'date_from'))
    if date_to is not None:
        qs = qs.filter(date__lte=_parse_date(date_to, 'date_to'))
    if category is not None:
        qs = qs.filter(category=resolve_category(category))
    qs = qs.select_related('category').order_by('date', 'id')
    if limit is not None:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            raise ValueError(f"Ungültiges Limit: {limit!r}")
        if limit <= 0:
            raise ValueError("Limit muss größer als 0 sein.")
        qs = qs[:limit]
    return _with_attachment_counts([serialize_booking(b) for b in qs])


def list_due_bookings(days_before_due=None, include_overdue=True, include_due_soon=True, limit=None):
    """Read-only equivalent of alerts.checks: due_soon + overdue planned bookings.

    Deliberately does not call alerts.checks.check_due_soon/check_overdue, since
    those persist Alert rows and send mail as a side effect — this tool only reads.
    """
    if days_before_due is None:
        days_before_due = AlertConfig.get().days_before_due
    else:
        try:
            days_before_due = int(days_before_due)
        except (TypeError, ValueError):
            raise ValueError(f"Ungültiges days_before_due: {days_before_due!r}")

    if limit is not None:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            raise ValueError(f"Ungültiges Limit: {limit!r}")
        if limit <= 0:
            raise ValueError("Limit muss größer als 0 sein.")

    today = date_type.today()
    due_date = today + timedelta(days=days_before_due)

    result = []
    if include_overdue:
        overdue = Booking.objects.filter(
            status='planned', date__lt=today
        ).select_related('category').order_by('date', 'id')
        for booking in overdue:
            item = serialize_booking(booking)
            item['due_state'] = 'overdue'
            item['days_until_due'] = (booking.date - today).days
            result.append(item)
    if include_due_soon:
        due_soon = Booking.objects.filter(
            status='planned', date__gte=today, date__lte=due_date
        ).select_related('category').order_by('date', 'id')
        for booking in due_soon:
            item = serialize_booking(booking)
            item['due_state'] = 'due_soon'
            item['days_until_due'] = (booking.date - today).days
            result.append(item)

    result.sort(key=lambda item: (item['date'], item['id']))
    if limit is not None:
        result = result[:limit]
    return _with_attachment_counts(result)


def list_categories():
    return [
        {
            'name': category.name,
            'category_type': category.category_type,
            'icon': category.icon,
            'color': category.color,
        }
        for category in Category.objects.order_by('name')
    ]


def _get_booking_or_raise(booking_id):
    try:
        return Booking.objects.get(pk=booking_id)
    except Booking.DoesNotExist:
        raise ValueError(f"Buchung mit ID {booking_id} nicht gefunden.")


def add_booking_attachment(booking_id, filename, content_base64):
    booking = _get_booking_or_raise(booking_id)

    filename = (filename or '').strip()
    if not filename:
        raise ValueError("Dateiname darf nicht leer sein.")

    if not content_base64:
        raise ValueError("content_base64 darf nicht leer sein.")
    try:
        data = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, TypeError, ValueError):
        raise ValueError("content_base64 ist kein gültiges Base64.")

    max_size = MCP_MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
    if len(data) > max_size:
        raise ValueError(
            f"Datei zu groß für den MCP-Upload. Maximale (dekodierte) Größe: "
            f"{MCP_MAX_ATTACHMENT_SIZE_MB} MB."
        )

    upload = SimpleUploadedFile(filename, data)
    try:
        attachment = handle_upload(upload, booking)
    except ValidationError as exc:
        raise ValueError('; '.join(exc.messages))

    return serialize_attachment(attachment)


def list_booking_attachments(booking_id):
    booking = _get_booking_or_raise(booking_id)
    attachments = get_attachments_for(booking)
    return [serialize_attachment(a, include_url=True) for a in attachments]


def delete_booking_attachment(attachment_id):
    if not delete_attachment_service(attachment_id):
        raise ValueError(f"Anhang mit ID {attachment_id} nicht gefunden.")
    return {'success': True, 'attachment_id': attachment_id}


# ---------------------------------------------------------------------------
# Time tracking
# ---------------------------------------------------------------------------

def list_clients():
    return [{'name': client.name, 'notes': client.notes} for client in Client.objects.order_by('name')]


def list_time_entries(date_from=None, date_to=None, client=None, billed=None, limit=None):
    qs = TimeEntry.objects.all()
    if date_from is not None:
        qs = qs.filter(date__gte=_parse_date(date_from, 'date_from'))
    if date_to is not None:
        qs = qs.filter(date__lte=_parse_date(date_to, 'date_to'))
    if client is not None:
        qs = qs.filter(client=resolve_client(client))
    if billed is not None:
        qs = qs.filter(billed=bool(billed))
    qs = qs.select_related('client').order_by('-date', '-created_at')
    if limit is not None:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            raise ValueError(f"Ungültiges Limit: {limit!r}")
        if limit <= 0:
            raise ValueError("Limit muss größer als 0 sein.")
        qs = qs[:limit]
    return [serialize_time_entry(entry) for entry in qs]


def _validate_duration(value):
    try:
        duration_dec = Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError):
        raise ValueError(f"Ungültige Dauer: {value!r}")
    if duration_dec <= 0:
        raise ValueError("Dauer muss größer als 0 sein.")
    return duration_dec


def _validate_hourly_rate(value):
    try:
        rate_dec = Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError):
        raise ValueError(f"Ungültiger Stundensatz: {value!r}")
    if rate_dec < 0:
        raise ValueError("Stundensatz darf nicht negativ sein.")
    return rate_dec


def create_time_entry(client, date, duration, hourly_rate, description, notes='', billed=False):
    entry_date = _parse_date(date)

    description = (description or '').strip()
    if not description:
        raise ValueError("Beschreibung darf nicht leer sein.")

    duration_dec = _validate_duration(duration)
    rate_dec = _validate_hourly_rate(hourly_rate)
    client_obj = resolve_client(client)

    entry = TimeEntry.objects.create(
        client=client_obj,
        date=entry_date,
        duration=duration_dec,
        hourly_rate=rate_dec,
        description=description,
        notes=notes or '',
        billed=bool(billed),
    )
    return serialize_time_entry(entry)


def update_time_entry(entry_id, client=None, date=None, duration=None, hourly_rate=None,
                       description=None, notes=None, billed=None):
    try:
        entry = TimeEntry.objects.get(pk=entry_id)
    except TimeEntry.DoesNotExist:
        raise ValueError(f"Zeiteintrag mit ID {entry_id} nicht gefunden.")

    if client is not None:
        entry.client = resolve_client(client)
    if date is not None:
        entry.date = _parse_date(date)
    if duration is not None:
        entry.duration = _validate_duration(duration)
    if hourly_rate is not None:
        entry.hourly_rate = _validate_hourly_rate(hourly_rate)
    if description is not None:
        description = description.strip()
        if not description:
            raise ValueError("Beschreibung darf nicht leer sein.")
        entry.description = description
    if notes is not None:
        entry.notes = notes
    if billed is not None:
        entry.billed = bool(billed)

    entry.save()
    return serialize_time_entry(entry)


# ---------------------------------------------------------------------------
# Recurring series
# ---------------------------------------------------------------------------

def list_recurring_series(category=None, interval=None, limit=None):
    qs = RecurringSeries.objects.select_related('category').order_by('-created_at')
    if category is not None:
        qs = qs.filter(category=resolve_category(category))
    if interval is not None:
        valid_intervals = dict(RecurringSeries.INTERVAL_CHOICES)
        if interval not in valid_intervals:
            raise ValueError(f"Ungültiges Intervall '{interval}'. Erlaubt: {', '.join(valid_intervals)}.")
        qs = qs.filter(interval=interval)
    if limit is not None:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            raise ValueError(f"Ungültiges Limit: {limit!r}")
        if limit <= 0:
            raise ValueError("Limit muss größer als 0 sein.")
        qs = qs[:limit]
    return [serialize_series(series) for series in qs]


def create_recurring_series(description, amount, interval, start_date, category,
                             end_date=None, notes='', generate_bookings=True):
    description = (description or '').strip()
    if not description:
        raise ValueError("Beschreibung darf nicht leer sein.")

    amount_dec = _parse_amount(amount)
    if amount_dec == 0:
        raise ValueError("Betrag darf nicht 0 sein.")

    valid_intervals = dict(RecurringSeries.INTERVAL_CHOICES)
    if interval not in valid_intervals:
        raise ValueError(f"Ungültiges Intervall '{interval}'. Erlaubt: {', '.join(valid_intervals)}.")

    start = _parse_date(start_date, 'start_date')
    end = _parse_date(end_date, 'end_date') if end_date is not None else None
    if end is not None and end < start:
        raise ValueError("Enddatum darf nicht vor dem Startdatum liegen.")

    category_obj = resolve_category(category)

    series = RecurringSeries.objects.create(
        description=description,
        amount=amount_dec,
        interval=interval,
        start_date=start,
        end_date=end,
        category=category_obj,
        notes=notes or '',
    )

    generated_bookings = None
    if generate_bookings:
        generated_bookings = len(create_series_bookings(series))

    result = serialize_series(series)
    if generated_bookings is not None:
        result['generated_bookings'] = generated_bookings
    return result
