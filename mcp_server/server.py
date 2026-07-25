"""
FastMCP tool definitions for MoneyPlan.

Every tool is a thin async adapter: validate input shape, hand off to the
synchronous logic in `mcp_server.logic` (run in a worker thread via
`sync_to_async`, since Django's ORM refuses direct sync calls from an async
context), and return a JSON-serializable result. All business rules and
validation live in `logic.py` so they can be unit-tested without MCP/async
plumbing.
"""
from asgiref.sync import sync_to_async
from mcp.server.fastmcp import FastMCP

from . import logic

mcp = FastMCP(
    name="MoneyPlan",
    instructions=(
        "Werkzeuge fuer die MoneyPlan-Haushaltsplanung: Buchungen anlegen und lesen, "
        "faellige/ueberfaellige Buchungen pruefen, Zeiterfassung sowie Serienbuchungen. "
        "Kategorien und Kunden werden per eindeutigem Namen referenziert - bei Bedarf "
        "list_categories/list_clients aufrufen, um gueltige Namen zu ermitteln."
    ),
    stateless_http=True,
)


@mcp.tool()
async def create_booking(
    date: str,
    description: str,
    amount: float,
    category: str,
    status: str = "planned",
    notes: str = "",
    series_id: int | None = None,
    liability_id: int | None = None,
) -> dict:
    """Legt eine neue Buchung an.

    date: Datum im Format YYYY-MM-DD.
    amount: Betrag; positiv = Einnahme, negativ = Ausgabe. Darf nicht 0 sein.
    category: Name einer bestehenden Kategorie (siehe list_categories).
    status: 'planned' (Geplant) oder 'booked' (Gebucht). Default: 'planned'.
    series_id / liability_id: optionale IDs einer bestehenden Serie bzw. Verbindlichkeit.
    """
    return await sync_to_async(logic.create_booking, thread_sensitive=True)(
        date, description, amount, category, status, notes, series_id, liability_id
    )


@mcp.tool()
async def list_planned_bookings(
    date_from: str | None = None,
    date_to: str | None = None,
    category: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Listet ausschliesslich geplante Buchungen (status='planned'), optional gefiltert
    nach Datumsbereich (YYYY-MM-DD), Kategorie (Name oder ID) und/oder begrenzt auf die
    ersten `limit` Treffer (sortiert nach Datum aufsteigend). Gebuchte Buchungen werden
    nie zurueckgegeben."""
    return await sync_to_async(logic.list_planned_bookings, thread_sensitive=True)(
        date_from, date_to, category, limit
    )


@mcp.tool()
async def list_due_bookings(
    days_before_due: int | None = None,
    include_overdue: bool = True,
    include_due_soon: bool = True,
    limit: int | None = None,
) -> list[dict]:
    """Listet faellige (due_soon) und ueberfaellige (overdue) geplante Buchungen,
    analog zur Alert-Logik der App - rein lesend, es werden keine Alert-Datensaetze
    angelegt oder E-Mails versendet.

    days_before_due: Vorlauf in Tagen fuer 'faellig'; Default aus AlertConfig (Singleton).
    include_overdue / include_due_soon: je Default True, um eine der beiden Gruppen auszublenden.
    limit: optionale Begrenzung der Trefferanzahl (sortiert nach Datum aufsteigend).
    """
    return await sync_to_async(logic.list_due_bookings, thread_sensitive=True)(
        days_before_due, include_overdue, include_due_soon, limit
    )


@mcp.tool()
async def list_categories() -> list[dict]:
    """Listet alle Kategorien mit Name und Typ - zur Aufloesung von Kategorie-Namen
    fuer create_booking/create_recurring_series."""
    return await sync_to_async(logic.list_categories, thread_sensitive=True)()


@mcp.tool()
async def list_clients() -> list[dict]:
    """Listet alle Kunden (Zeiterfassung) - zur Aufloesung von Kunden-Namen fuer
    create_time_entry."""
    return await sync_to_async(logic.list_clients, thread_sensitive=True)()


@mcp.tool()
async def list_time_entries(
    date_from: str | None = None,
    date_to: str | None = None,
    client: str | None = None,
    billed: bool | None = None,
) -> list[dict]:
    """Listet Zeiterfassungseintraege, optional gefiltert nach Datumsbereich
    (YYYY-MM-DD), Kunden-Name und Abrechnungsstatus."""
    return await sync_to_async(logic.list_time_entries, thread_sensitive=True)(
        date_from, date_to, client, billed
    )


@mcp.tool()
async def create_time_entry(
    client: str,
    date: str,
    duration: float,
    hourly_rate: float,
    description: str,
    notes: str = "",
    billed: bool = False,
) -> dict:
    """Erfasst einen neuen Zeiteintrag.

    client: Name eines bestehenden Kunden (siehe list_clients).
    date: Datum im Format YYYY-MM-DD.
    duration: Dauer in Stunden (z.B. 1.5 = 1h 30min), muss > 0 sein.
    hourly_rate: Stundensatz, darf nicht negativ sein.
    """
    return await sync_to_async(logic.create_time_entry, thread_sensitive=True)(
        client, date, duration, hourly_rate, description, notes, billed
    )


@mcp.tool()
async def update_time_entry(
    entry_id: int,
    client: str | None = None,
    date: str | None = None,
    duration: float | None = None,
    hourly_rate: float | None = None,
    description: str | None = None,
    notes: str | None = None,
    billed: bool | None = None,
) -> dict:
    """Aendert einen bestehenden Zeiteintrag. Nur uebergebene Felder werden geaendert."""
    return await sync_to_async(logic.update_time_entry, thread_sensitive=True)(
        entry_id, client, date, duration, hourly_rate, description, notes, billed
    )


@mcp.tool()
async def list_recurring_series() -> list[dict]:
    """Listet alle Serienbuchungen (RecurringSeries)."""
    return await sync_to_async(logic.list_recurring_series, thread_sensitive=True)()


@mcp.tool()
async def create_recurring_series(
    description: str,
    amount: float,
    interval: str,
    start_date: str,
    category: str,
    end_date: str | None = None,
    notes: str = "",
    generate_bookings: bool = True,
) -> dict:
    """Legt eine neue Serienbuchung an.

    interval: 'weekly', 'monthly', 'quarterly', 'semi_annual' oder 'yearly'.
    start_date / end_date: Format YYYY-MM-DD. Ohne end_date werden 2 Jahre generiert.
    generate_bookings: wenn True (Default), werden die zugehoerigen geplanten
    Buchungen sofort erzeugt (wie im UI-Wizard).
    """
    return await sync_to_async(logic.create_recurring_series, thread_sensitive=True)(
        description, amount, interval, start_date, category, end_date, notes, generate_bookings
    )
