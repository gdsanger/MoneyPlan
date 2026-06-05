"""AI-powered financial overview service."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from ai.providers.base import AIMessage
from ai.service import complete
from ai.exceptions import AIServiceError, AIProviderNotConfigured
from bookings.services import (
    get_current_balance,
    get_planned_income,
    get_planned_expenses,
    get_available_funds,
    get_forecast,
    get_top_categories,
    get_year_overview,
    get_total_liabilities,
    get_liabilities_overview,
    get_total_assets,
    get_net_worth,
    get_assets_by_category,
    get_due_this_month,
)
from alerts.models import Alert
from tasks.models import Task


OverviewMode = Literal['short', 'detailed']


@dataclass
class FinancialOverviewResult:
    """Result of AI financial overview generation."""
    content: str
    mode: OverviewMode
    ai_provider: str
    ai_model: str


def _format_euro(value: Decimal) -> str:
    """Format Decimal as German currency string."""
    formatted = f"{value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"{formatted} €"


def build_financial_snapshot() -> dict:
    """
    Aggregate current financial data into a structured snapshot for AI analysis.

    Returns:
        dict: Structured financial data summary
    """
    today = date.today()
    forecast = get_forecast(months=3)
    year_data = get_year_overview(today.year)
    top_categories = get_top_categories(limit=5)
    liabilities = get_liabilities_overview()
    assets_by_category = get_assets_by_category()
    due_bookings = list(get_due_this_month()[:10])
    alerts = list(Alert.objects.all()[:10])
    open_tasks = Task.objects.filter(status='open').count()

    # Year summary
    year_income = sum(m['income_booked'] + m['income_planned'] for m in year_data)
    year_expenses = sum(m['expenses_booked'] + m['expenses_planned'] for m in year_data)
    year_result = year_income - year_expenses

    # Current month from year data
    current_month = next((m for m in year_data if m['is_current']), None)

    # Time tracking
    tt_unbilled = Decimal('0.00')
    tt_forecast = None
    try:
        from timetracking.services import get_unbilled_total, get_forecast_entry
        tt_unbilled = get_unbilled_total()
        tt_forecast = get_forecast_entry()
    except ImportError:
        pass

    open_liabilities = [item for item in liabilities if not item['is_closed']]

    return {
        'today': today.isoformat(),
        'current_balance': get_current_balance(),
        'planned_income': get_planned_income(),
        'planned_expenses': get_planned_expenses(),
        'available_funds_month': get_available_funds(month=today),
        'available_funds_total': get_available_funds(),
        'total_assets': get_total_assets(),
        'total_liabilities': get_total_liabilities(),
        'net_worth': get_net_worth(),
        'forecast': forecast,
        'year_income': year_income,
        'year_expenses': year_expenses,
        'year_result': year_result,
        'current_month': current_month,
        'top_categories': top_categories,
        'open_liabilities': open_liabilities,
        'assets_by_category': assets_by_category,
        'due_bookings': due_bookings,
        'alerts': alerts,
        'open_tasks_count': open_tasks,
        'tt_unbilled': tt_unbilled,
        'tt_forecast': tt_forecast,
    }


def _snapshot_to_prompt_text(snapshot: dict, mode: OverviewMode) -> str:
    """Convert financial snapshot to structured text for the AI prompt."""
    lines = [
        f"Stand: {snapshot['today']}",
        "",
        "=== LIQUIDITÄT ===",
        f"Aktueller Kontostand (gebucht): {_format_euro(snapshot['current_balance'])}",
        f"Verfügbare Mittel (aktueller Monat): {_format_euro(snapshot['available_funds_month'])}",
        f"Verfügbare Mittel (Gesamt inkl. geplant): {_format_euro(snapshot['available_funds_total'])}",
        f"Offene Einnahmen (geplant): {_format_euro(snapshot['planned_income'])}",
        f"Offene Ausgaben (geplant): {_format_euro(snapshot['planned_expenses'])}",
        "",
        "=== VERMÖGEN & VERBINDLICHKEITEN ===",
        f"Gesamtvermögen: {_format_euro(snapshot['total_assets'])}",
        f"Offene Verbindlichkeiten: {_format_euro(snapshot['total_liabilities'])}",
        f"Nettovermögen: {_format_euro(snapshot['net_worth'])}",
    ]

    if snapshot['assets_by_category']:
        lines.append("")
        lines.append("Vermögen nach Kategorie:")
        for item in snapshot['assets_by_category']:
            lines.append(f"  - {item['label']}: {_format_euro(item['total'])} ({item['percent']}%)")

    if snapshot['open_liabilities']:
        lines.append("")
        lines.append("Offene Verbindlichkeiten:")
        for item in snapshot['open_liabilities'][:5]:
            liability = item['liability']
            lines.append(
                f"  - {liability.name}: Restschuld {_format_euro(item['remaining'])} "
                f"({item['repaid_percent']}% getilgt)"
            )

    lines.extend([
        "",
        "=== FORECAST (+3 Monate) ===",
    ])
    for month in snapshot['forecast']:
        lines.append(
            f"  {month['label']}: Einnahmen {_format_euro(month['planned_income'])}, "
            f"Ausgaben {_format_euro(month['planned_expenses'])}, "
            f"Projizierter Saldo {_format_euro(month['projected_balance'])}"
        )

    if snapshot['current_month']:
        cm = snapshot['current_month']
        lines.extend([
            "",
            f"=== AKTUELLER MONAT ({cm['label']}) ===",
            f"Einnahmen (gebucht): {_format_euro(cm['income_booked'])}",
            f"Einnahmen (geplant): {_format_euro(cm['income_planned'])}",
            f"Ausgaben (gebucht): {_format_euro(cm['expenses_booked'])}",
            f"Ausgaben (geplant): {_format_euro(cm['expenses_planned'])}",
            f"Ergebnis (gesamt): {_format_euro(cm['result_total'])}",
        ])

    lines.extend([
        "",
        f"=== JAHR {date.today().year} ===",
        f"Gesamteinnahmen: {_format_euro(snapshot['year_income'])}",
        f"Gesamtausgaben: {_format_euro(snapshot['year_expenses'])}",
        f"Jahresergebnis: {_format_euro(snapshot['year_result'])}",
    ])

    if snapshot['top_categories']:
        lines.append("")
        lines.append("Top Ausgabenkategorien (letzte 3 Monate):")
        for item in snapshot['top_categories']:
            lines.append(f"  - {item['category'].name}: {_format_euro(item['total'])}")

    if snapshot['due_bookings']:
        lines.append("")
        lines.append(f"Fällige Buchungen diesen Monat ({len(snapshot['due_bookings'])}):")
        for booking in snapshot['due_bookings'][:5]:
            lines.append(
                f"  - {booking.date.strftime('%d.%m.%Y')}: {booking.description} "
                f"{_format_euro(booking.amount)}"
            )

    if snapshot['alerts']:
        lines.append("")
        lines.append(f"Aktive Alerts ({len(snapshot['alerts'])}):")
        for alert in snapshot['alerts'][:5]:
            lines.append(f"  - [{alert.get_alert_type_display()}] {alert.message[:80]}")

    if snapshot['open_tasks_count']:
        lines.append(f"\nOffene Aufgaben: {snapshot['open_tasks_count']}")

    if snapshot['tt_unbilled'] > 0:
        lines.append(f"Nicht abgerechnete Zeiten: {_format_euro(snapshot['tt_unbilled'])}")
        if snapshot['tt_forecast']:
            lines.append(
                f"  Prognose-Eintrag: {snapshot['tt_forecast']['date'].strftime('%d.%m.%Y')} "
                f"{_format_euro(snapshot['tt_forecast']['amount'])}"
            )

    if mode == 'detailed':
        lines.extend([
            "",
            "=== DETAILLIERTE MONATSÜBERSICHT (Jahr) ===",
        ])
        for month in snapshot.get('_year_months', []):
            lines.append(
                f"  {month['label']}: E {_format_euro(month['income_booked'] + month['income_planned'])}, "
                f"A {_format_euro(month['expenses_booked'] + month['expenses_planned'])}, "
                f"Ergebnis {_format_euro(month['result_total'])}"
            )

    return "\n".join(lines)


def generate_financial_overview(mode: OverviewMode = 'short') -> FinancialOverviewResult:
    """
    Generate an AI-powered financial overview based on current data.

    Args:
        mode: 'short' for brief summary, 'detailed' for comprehensive analysis

    Returns:
        FinancialOverviewResult with AI-generated content

    Raises:
        AIProviderNotConfigured: If AI service is not configured
        AIServiceError: If provider API call fails
    """
    snapshot = build_financial_snapshot()

    if mode == 'detailed':
        snapshot['_year_months'] = get_year_overview(date.today().year)

    data_text = _snapshot_to_prompt_text(snapshot, mode)

    if mode == 'short':
        system_prompt = """Du bist ein Finanzberater für eine persönliche Finanzplanungs-App.
Erstelle einen prägnanten Kurzüberblick auf Deutsch basierend auf den bereitgestellten Finanzdaten.
Sei sachlich, klar und handlungsorientiert. Verwende Markdown-Formatierung (## für Überschriften, - für Listen).
Keine Einleitung wie "Hier ist Ihr Überblick" — starte direkt mit dem Inhalt."""
        user_prompt = f"""Analysiere diese Finanzdaten und erstelle einen Kurzüberblick (max. 250 Wörter):

{data_text}

Struktur:
## Gesamtlage
(2-3 Sätze zur aktuellen finanziellen Situation)

## Ausblick
(Was erwartet mich in den nächsten 3 Monaten?)

## Handlungsempfehlung
(1-2 konkrete, priorisierte Empfehlungen)

## Risiken
(Nur wenn relevant — z.B. Liquiditätsengpass, überfällige Buchungen)"""
        max_tokens = 800
        feature = "financial_overview_short"
    else:
        system_prompt = """Du bist ein Finanzberater für eine persönliche Finanzplanungs-App.
Erstelle eine ausführliche Finanzanalyse auf Deutsch basierend auf den bereitgestellten Finanzdaten.
Sei sachlich, strukturiert und handlungsorientiert. Verwende Markdown-Formatierung.
Keine Einleitung wie "Hier ist Ihre Analyse" — starte direkt mit dem Inhalt."""
        user_prompt = f"""Analysiere diese Finanzdaten und erstelle eine detaillierte Finanzübersicht:

{data_text}

Struktur:
## Executive Summary
(Kompakte Zusammenfassung der Gesamtsituation)

## Liquidität & Cashflow
(Aktueller Stand, verfügbare Mittel, geplante Ein- und Ausgaben)

## Vermögenslage
(Vermögen, Verbindlichkeiten, Nettovermögen — mit Einordnung)

## Prognose & Entwicklung
(3-Monats-Forecast interpretieren, Trends erkennen, Jahresperspektive)

## Ausgabenanalyse
(Wichtigste Kategorien, Auffälligkeiten)

## Verbindlichkeiten & Fälligkeiten
(Offene Schulden, anstehende Zahlungen, Alerts)

## Handlungsempfehlungen
(Konkrete, priorisierte Maßnahmen — nummerierte Liste)

## Chancen & Risiken
(Positive Entwicklungen und potenzielle Gefahren)"""
        max_tokens = 2500
        feature = "financial_overview_detailed"

    try:
        response = complete(
            messages=[AIMessage(role="user", content=user_prompt)],
            system_prompt=system_prompt,
            feature=feature,
            max_tokens=max_tokens,
        )
    except AIProviderNotConfigured:
        raise
    except Exception as e:
        raise AIServiceError(f"AI provider failed: {str(e)}")

    return FinancialOverviewResult(
        content=response.content.strip(),
        mode=mode,
        ai_provider=response.provider,
        ai_model=response.model,
    )
