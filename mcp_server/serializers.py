"""JSON-serializable dict views of the models exposed via MCP tools."""
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal('0.01')


def serialize_booking(booking):
    return {
        'id': booking.id,
        'date': booking.date.isoformat(),
        'description': booking.description,
        'amount': str(booking.amount),
        'status': booking.status,
        'category': booking.category.name,
        'series_id': booking.series_id,
        'liability_id': booking.liability_id,
        'notes': booking.notes,
    }


def serialize_time_entry(entry):
    return {
        'id': entry.id,
        'client': entry.client.name,
        'date': entry.date.isoformat(),
        'duration': str(entry.duration),
        'hourly_rate': str(entry.hourly_rate),
        # duration * hourly_rate multiplies two 2-decimal Decimals, yielding 4
        # decimal places (e.g. 150.0000) — quantize back to money precision.
        'amount': str(entry.amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)),
        'description': entry.description,
        'notes': entry.notes,
        'billed': entry.billed,
    }


def serialize_series(series):
    return {
        'id': series.id,
        'description': series.description,
        'amount': str(series.amount),
        'interval': series.interval,
        'start_date': series.start_date.isoformat(),
        'end_date': series.end_date.isoformat() if series.end_date else None,
        'category': series.category.name,
        'notes': series.notes,
    }
