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
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from . import logic

mcp = FastMCP(
    name="MoneyPlan",
    instructions=(
        "Werkzeuge fuer die MoneyPlan-Haushaltsplanung: Buchungen anlegen und lesen, "
        "faellige/ueberfaellige Buchungen pruefen, Zeiterfassung sowie Serienbuchungen. "
        "Kategorien und Kunden werden per eindeutigem Namen referenziert - bei Bedarf "
        "list_categories/list_clients aufrufen, um gueltige Namen zu ermitteln. "
        "Belege/Rechnungen koennen per add_booking_attachment (Base64) an eine "
        "Buchung angehaengt werden. Tags (Schlagworte je Dimension, z.B. Projekt/"
        "Kunde/Kostenstelle) werden ausschliesslich im UI angelegt/gepflegt - "
        "list_tags liefert die bestehenden Namen, create_booking/create_time_entry "
        "und set_booking_tags/set_time_entry_tags ordnen sie zu, list_planned_bookings/"
        "list_due_bookings/list_time_entries filtern danach."
    ),
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "mpmcp.angerlabs.de",      # der Weg über NPM (produktiv)
            "127.0.0.1:8888",
            "localhost:8888",
            "178.105.124.17:8888",     # nur für deinen direkten IP-Test
        ],
        allowed_origins=["https://mpmcp.angerlabs.de"],
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
    tags: list[str] | None = None,
) -> dict:
    """Legt eine neue Buchung an.

    date: Datum im Format YYYY-MM-DD.
    amount: Betrag; positiv = Einnahme, negativ = Ausgabe. Darf nicht 0 sein.
    category: Name einer bestehenden Kategorie (siehe list_categories).
    status: 'planned' (Geplant) oder 'booked' (Gebucht). Default: 'planned'.
    series_id / liability_id: optionale IDs einer bestehenden Serie bzw. Verbindlichkeit.
    tags: optionale Liste bestehender Tag-Namen oder -IDs (siehe list_tags). Ein
    Tag-Name muss innerhalb seiner Dimension eindeutig sein; kommt derselbe Name
    in mehreren Dimensionen vor, die Tag-ID statt des Namens verwenden.
    """
    return await sync_to_async(logic.create_booking, thread_sensitive=True)(
        date, description, amount, category, status, notes, series_id, liability_id, tags
    )


@mcp.tool()
async def list_planned_bookings(
    date_from: str | None = None,
    date_to: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    tag_kind: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Listet ausschliesslich geplante Buchungen (status='planned'), optional gefiltert
    nach Datumsbereich (YYYY-MM-DD), Kategorie (Name oder ID), Tag (Name oder ID),
    Tag-Dimension (tag_kind, z.B. 'projekt') und/oder begrenzt auf die ersten `limit`
    Treffer (sortiert nach Datum aufsteigend). Gebuchte Buchungen werden nie
    zurueckgegeben. Jeder Eintrag enthaelt 'attachment_count' - Anzahl bereits
    angehaengter Belege (siehe add_booking_attachment/list_booking_attachments) sowie
    'tags' - Liste der zugeordneten Tags."""
    return await sync_to_async(logic.list_planned_bookings, thread_sensitive=True)(
        date_from, date_to, category, tag, tag_kind, limit
    )


@mcp.tool()
async def list_due_bookings(
    days_before_due: int | None = None,
    include_overdue: bool = True,
    include_due_soon: bool = True,
    tag: str | None = None,
    tag_kind: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Listet faellige (due_soon) und ueberfaellige (overdue) geplante Buchungen,
    analog zur Alert-Logik der App - rein lesend, es werden keine Alert-Datensaetze
    angelegt oder E-Mails versendet.

    days_before_due: Vorlauf in Tagen fuer 'faellig'; Default aus AlertConfig (Singleton).
    include_overdue / include_due_soon: je Default True, um eine der beiden Gruppen auszublenden.
    tag / tag_kind: optionaler Filter nach Tag (Name oder ID) bzw. Tag-Dimension.
    limit: optionale Begrenzung der Trefferanzahl (sortiert nach Datum aufsteigend).
    Jeder Eintrag enthaelt 'attachment_count' - Anzahl bereits angehaengter Belege
    sowie 'tags' - Liste der zugeordneten Tags.
    """
    return await sync_to_async(logic.list_due_bookings, thread_sensitive=True)(
        days_before_due, include_overdue, include_due_soon, tag, tag_kind, limit
    )


@mcp.tool()
async def list_categories() -> list[dict]:
    """Listet alle Kategorien mit Name und Typ - zur Aufloesung von Kategorie-Namen
    fuer create_booking/create_recurring_series.
    Jeder Eintrag enthaelt 'description' - kurze Erklaerung zur Kategorie, die
    bei der Auswahl der richtigen Kategorie (z.B. privat vs. geschaeftlich) helfen soll."""
    return await sync_to_async(logic.list_categories, thread_sensitive=True)()


@mcp.tool()
async def list_tags(kind: str | None = None, include_archived: bool = False) -> list[dict]:
    """Listet Tags (Schlagworte) inkl. Dimension ('kind') und Farbe - zur Aufloesung
    von Tag-Namen fuer create_booking/create_time_entry/set_booking_tags/
    set_time_entry_tags sowie zum Filtern in list_planned_bookings/list_due_bookings/
    list_time_entries.

    kind: optionale Dimension ('projekt', 'kunde', 'kostenstelle' oder 'sonstiges').
    include_archived: Default False (nur aktive Tags); True zeigt auch archivierte.
    Tags werden manuell im UI gepflegt - dieses Tool legt keine neuen Tags an.
    """
    return await sync_to_async(logic.list_tags, thread_sensitive=True)(kind, include_archived)


@mcp.tool()
async def set_booking_tags(booking_id: int, tags: list[str]) -> dict:
    """Ersetzt die komplette Tag-Zuordnung einer Buchung (nicht additiv - vorhandene
    Tags, die nicht in der Liste enthalten sind, werden entfernt). Leere Liste
    entfernt alle Tags.

    booking_id: ID einer bestehenden Buchung.
    tags: Liste bestehender Tag-Namen oder -IDs (siehe list_tags).
    """
    return await sync_to_async(logic.set_booking_tags, thread_sensitive=True)(
        booking_id, tags
    )


@mcp.tool()
async def add_booking_attachment(
    booking_id: int,
    filename: str,
    content_base64: str,
) -> dict:
    """Haengt einen Beleg/eine Rechnung (Base64-kodiert) als echten Datei-Anhang an
    eine bestehende Buchung an - ueber dieselbe attachments-App wie das Web-UI.

    NUR fuer Mini-Dateien geeignet (siehe Limit unten): Base64 laeuft durch den
    Agenten-Kontext und ein Tool-Output-Cap von grob 30K Zeichen entspricht nur
    ~20 KB Datei - bei groesseren Dateien wird die Base64-Ausgabe vom Agenten
    gechunkt und laeuft Gefahr, beim Wiederzusammensetzen zu korrumpieren.
    Fuer echte Belege/Rechnungen stattdessen den Token-authentifizierten
    HTTP-Upload verwenden (multipart, Bytes gehen direkt an den Server, nicht
    durch den Agenten-Kontext):
    curl -H "Authorization: Bearer <token>" -F "file=@beleg.pdf" \\
        https://mpmcp.angerlabs.de/api/bookings/<booking_id>/attachment/

    booking_id: ID einer bestehenden Buchung.
    filename: Dateiname inkl. Endung (z.B. 'rechnung_2026-08.pdf').
    content_base64: Dateiinhalt Base64-kodiert. Gedacht fuer Belege < 100 KB;
    MCP-seitig auf 2 MB (dekodiert) begrenzt, unabhaengig vom serverseitigen
    Limit. Der tatsaechliche Dateityp wird serverseitig per Inhaltspruefung
    (nicht anhand des Dateinamens) validiert - erlaubt sind u.a. PDF, gaengige
    Bildformate, Office-Dokumente, CSV und Text; zu große oder nicht erlaubte
    Dateien fuehren zu einem Fehler statt einem stillen Bypass.
    """
    return await sync_to_async(logic.add_booking_attachment, thread_sensitive=True)(
        booking_id, filename, content_base64
    )


@mcp.tool()
async def list_booking_attachments(booking_id: int) -> list[dict]:
    """Listet alle Anhaenge (Belege/Rechnungen) einer Buchung, neueste zuerst,
    inkl. relativer Download-URL ('url')."""
    return await sync_to_async(logic.list_booking_attachments, thread_sensitive=True)(
        booking_id
    )


@mcp.tool()
async def delete_booking_attachment(attachment_id: int) -> dict:
    """Loescht einen Anhang (Datei + Datensatz) anhand seiner attachment_id
    (siehe list_booking_attachments)."""
    return await sync_to_async(logic.delete_booking_attachment, thread_sensitive=True)(
        attachment_id
    )


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
    tag: str | None = None,
    tag_kind: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Listet Zeiterfassungseintraege, neueste zuerst, optional gefiltert nach
    Datumsbereich (YYYY-MM-DD), Kunde (Name oder ID), Abrechnungsstatus, Tag
    (Name oder ID), Tag-Dimension (tag_kind, z.B. 'projekt') und/oder begrenzt
    auf die ersten `limit` Treffer. Jeder Eintrag enthaelt 'amount'
    (= duration x hourly_rate, berechnet) sowie 'tags' - Liste der zugeordneten Tags."""
    return await sync_to_async(logic.list_time_entries, thread_sensitive=True)(
        date_from, date_to, client, billed, tag, tag_kind, limit
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
    tags: list[str] | None = None,
) -> dict:
    """Erfasst einen neuen Zeiteintrag.

    client: Name oder ID eines bestehenden Kunden (siehe list_clients).
    date: Datum im Format YYYY-MM-DD.
    duration: Dauer in Stunden (z.B. 1.5 = 1h 30min), muss > 0 sein.
    hourly_rate: Stundensatz, darf nicht negativ sein.
    tags: optionale Liste bestehender Tag-Namen oder -IDs (siehe list_tags). Ein
    Tag-Name muss innerhalb seiner Dimension eindeutig sein; kommt derselbe Name
    in mehreren Dimensionen vor, die Tag-ID statt des Namens verwenden.
    """
    return await sync_to_async(logic.create_time_entry, thread_sensitive=True)(
        client, date, duration, hourly_rate, description, notes, billed, tags
    )


@mcp.tool()
async def set_time_entry_tags(entry_id: int, tags: list[str]) -> dict:
    """Ersetzt die komplette Tag-Zuordnung eines Zeiteintrags (nicht additiv -
    vorhandene Tags, die nicht in der Liste enthalten sind, werden entfernt).
    Leere Liste entfernt alle Tags.

    entry_id: ID eines bestehenden Zeiteintrags.
    tags: Liste bestehender Tag-Namen oder -IDs (siehe list_tags).
    """
    return await sync_to_async(logic.set_time_entry_tags, thread_sensitive=True)(
        entry_id, tags
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
    """Aendert einen bestehenden Zeiteintrag. Nur uebergebene Felder werden
    geaendert. client kann Name oder ID sein."""
    return await sync_to_async(logic.update_time_entry, thread_sensitive=True)(
        entry_id, client, date, duration, hourly_rate, description, notes, billed
    )


@mcp.tool()
async def list_recurring_series(
    category: str | None = None,
    interval: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Listet Serienbuchungen (RecurringSeries), neueste zuerst, optional gefiltert
    nach Kategorie (Name oder ID), Intervall und/oder begrenzt auf die ersten
    `limit` Treffer. Jeder Eintrag enthaelt 'booking_count' - die Anzahl bereits
    erzeugter Buchungen dieser Serie."""
    return await sync_to_async(logic.list_recurring_series, thread_sensitive=True)(
        category, interval, limit
    )


@mcp.tool()
async def list_series_attachments(series_id: int) -> list[dict]:
    """Listet alle Anhaenge (z.B. Vertraege, Kuendigungen, Preisanpassungen) einer
    Serienbuchung (RecurringSeries), neueste zuerst, inkl. relativer Download-URL
    ('url'). Die Anhaenge haengen an der Serie selbst, nicht an einzelnen daraus
    erzeugten Buchungen (siehe list_booking_attachments fuer Anhaenge an
    einzelnen Buchungen)."""
    return await sync_to_async(logic.list_series_attachments, thread_sensitive=True)(
        series_id
    )


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


@mcp.tool()
async def extend_recurring_series(series_id: int, end_date: str) -> dict:
    """Verlaengert eine bestehende Serienbuchung bis zum angegebenen Enddatum
    (Format YYYY-MM-DD) und legt alle bis dahin fehlenden, noch nicht existierenden
    Buchungen als 'planned' mit dem aktuellen Betrag der Serie an (dublettenfrei).

    Nur Verlaengerung: end_date muss nach dem aktuellen Enddatum der Serie liegen,
    sonst wird ein Fehler ausgeloest. Wird auf maximal 10 Jahre ab Serienstart
    begrenzt (siehe 'capped_to_max_end_date' im Ergebnis). Archivierte Serien
    koennen nicht verlaengert werden."""
    return await sync_to_async(logic.extend_recurring_series, thread_sensitive=True)(
        series_id, end_date
    )
