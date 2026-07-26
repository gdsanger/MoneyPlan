"""
Rentabilität je Tag & Dimension (Epic #978).

Money and time are reported separately and never mixed: a booking's amount already
reflects any invoiced time (e.g. an outgoing invoice for billed hours), so adding
`duration × hourly_rate` on top would double-count that revenue. Hours and their
euro-value ("Zeitwert") are therefore always additional context next to the money
balance, never part of income/expenses/result.

All monetary values are Decimal, Brutto (as booked/planned), signed via separate
income/expenses/result fields (never mixed sign like Booking.amount).
"""
from collections import OrderedDict
from decimal import Decimal

from django.db.models import DecimalField, F, Sum
from django.db.models.functions import Coalesce

from bookings.models import Booking
from timetracking.models import TimeEntry
from .models import Tag

ZERO = Decimal('0.00')

_TOTAL_FIELDS = (
    'income_booked', 'expenses_booked', 'result_booked',
    'income_planned', 'expenses_planned', 'result_planned', 'result_total',
    'hours', 'time_value',
)


def _empty_totals() -> dict:
    return {field: ZERO for field in _TOTAL_FIELDS}


def _money_totals(bookings_qs) -> dict:
    """Booked/planned income & expenses (Brutto, both returned as positive numbers)."""
    def total(**filters):
        result = bookings_qs.filter(**filters).aggregate(total=Sum('amount'))['total']
        return abs(result) if result else ZERO

    return {
        'income_booked': total(status='booked', amount__gt=0),
        'expenses_booked': total(status='booked', amount__lt=0),
        'income_planned': total(status='planned', amount__gt=0),
        'expenses_planned': total(status='planned', amount__lt=0),
    }


def _time_totals(time_entries_qs) -> tuple[Decimal, Decimal]:
    """Hours and their euro-value (duration × hourly_rate) — kept out of the money balance."""
    aggregates = time_entries_qs.aggregate(
        hours=Coalesce(Sum('duration'), ZERO),
        time_value=Coalesce(
            Sum(F('duration') * F('hourly_rate'), output_field=DecimalField(max_digits=12, decimal_places=2)),
            ZERO,
        ),
    )
    return aggregates['hours'], aggregates['time_value']


def _build_row(tag, bookings_qs, time_entries_qs) -> dict:
    money = _money_totals(bookings_qs)
    hours, time_value = _time_totals(time_entries_qs)

    result_booked = money['income_booked'] - money['expenses_booked']
    result_planned = money['income_planned'] - money['expenses_planned']

    return {
        'tag': tag,
        'income_booked': money['income_booked'],
        'expenses_booked': money['expenses_booked'],
        'result_booked': result_booked,
        'income_planned': money['income_planned'],
        'expenses_planned': money['expenses_planned'],
        'result_planned': result_planned,
        'result_total': result_booked + result_planned,
        'hours': hours,
        'time_value': time_value,
        'revenue_per_hour': (money['income_booked'] / hours) if hours else None,
        'result_per_hour': (result_booked / hours) if hours else None,
    }


def _accumulate(totals: dict, row: dict) -> None:
    for field in _TOTAL_FIELDS:
        totals[field] += row[field]


def _distinct_tagged(qs):
    """
    Queryset of distinct tagged rows, without the M2M join used for `tags__isnull`.

    Aggregating directly on a `tags__isnull=False` queryset would sum each row once
    per matching tag (join fan-out), double-counting bookings/time entries tagged in
    more than one dimension. Resolving to distinct pks first and re-querying without
    the join keeps the aggregate correct.
    """
    ids = qs.filter(tags__isnull=False).values_list('pk', flat=True).distinct()
    return qs.model.objects.filter(pk__in=set(ids))


def get_tag_overview(start_date, end_date) -> dict:
    """
    Rentabilität je Tag (Entity) und aggregiert je Dimension (Tag.kind) im Zeitraum.

    Nur Tags mit mindestens einer Buchung oder einem Zeiteintrag im Zeitraum werden
    aufgeführt (keine leeren Zeilen für ungenutzte/archivierte Tags). Buchungen bzw.
    Zeiteinträge ganz ohne Tag werden separat unter 'untagged' ausgewiesen.

    Trägt eine Buchung mehrere Tags derselben Dimension (z. B. zwei Projekt-Tags),
    fließt ihr Betrag in beide Tag-Zeilen und damit auch doppelt in die Dimensions-
    summe ein — das ist beabsichtigt (jeder Tag muss für sich rentabel bewertbar sein).

    `grand_totals` ist davon bewusst ausgenommen: Trägt eine Buchung Tags aus
    mehreren Dimensionen (z. B. Projekt UND Kostenstelle), darf sie in der
    aggregierten Kopfzahl nur einmal zählen. Die Kopf-KPIs werden daher separat
    über die Menge der eindeutigen getaggten Buchungen/Zeiteinträge berechnet,
    nicht als Summe der Dimensions-/Tag-Zeilen.

    Returns:
        dict: {
            'groups': OrderedDict[kind] -> {'label': str, 'rows': [row, ...], 'totals': dict},
            'untagged': row | None,
            'grand_totals': dict,  # Distinct getaggte Buchungen/Zeiteinträge (ohne 'untagged'), je Buchung nur einmal gezählt
        }

        Jede `row` enthält (alle Decimal, Einnahmen/Ausgaben als positive Zahlen):
        tag, income_booked, expenses_booked, result_booked,
        income_planned, expenses_planned, result_planned, result_total,
        hours, time_value, revenue_per_hour, result_per_hour (letztere zwei None ohne Stunden).
    """
    period_bookings = Booking.objects.filter(date__gte=start_date, date__lte=end_date)
    period_time_entries = TimeEntry.objects.filter(date__gte=start_date, date__lte=end_date)

    tag_ids = set(
        period_bookings.filter(tags__isnull=False).values_list('tags', flat=True)
    ) | set(
        period_time_entries.filter(tags__isnull=False).values_list('tags', flat=True)
    )
    tags = Tag.objects.filter(id__in=tag_ids).order_by('kind', 'name')

    kind_labels = dict(Tag.KIND_CHOICES)
    groups = OrderedDict(
        (kind_key, {'label': kind_labels[kind_key], 'rows': [], 'totals': _empty_totals()})
        for kind_key, _ in Tag.KIND_CHOICES
    )

    for tag in tags:
        row = _build_row(
            tag,
            period_bookings.filter(tags=tag),
            period_time_entries.filter(tags=tag),
        )
        group = groups[tag.kind]
        group['rows'].append(row)
        _accumulate(group['totals'], row)

    # Dimensions ohne Aktivität im Zeitraum nicht anzeigen.
    groups = OrderedDict((kind, data) for kind, data in groups.items() if data['rows'])

    untagged_bookings = period_bookings.filter(tags__isnull=True)
    untagged_time_entries = period_time_entries.filter(tags__isnull=True)
    if untagged_bookings.exists() or untagged_time_entries.exists():
        untagged = _build_row(None, untagged_bookings, untagged_time_entries)
    else:
        untagged = None

    grand_totals = _build_row(None, _distinct_tagged(period_bookings), _distinct_tagged(period_time_entries))

    return {
        'groups': groups,
        'untagged': untagged,
        'grand_totals': grand_totals,
    }
