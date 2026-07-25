"""
Uniform name-based resolution for MCP tool inputs.

Category and Client are both referenced by their unique, human-readable
`name` field rather than by database id — MCP clients (AI agents) don't know
internal ids, and both models already enforce uniqueness on name.
"""
from bookings.models import Category
from timetracking.models import Client


def resolve_category(name) -> Category:
    """Resolve a Category by name (case-insensitive) or numeric id.

    MCP clients mostly know categories by name, but some tools accept the id
    surfaced in prior results (e.g. list_categories) - accept both rather than
    forcing an extra lookup round-trip.
    """
    if isinstance(name, int):
        try:
            return Category.objects.get(pk=name)
        except Category.DoesNotExist:
            raise ValueError(f"Kategorie mit ID {name} nicht gefunden.")

    name = (name or '').strip()
    if not name:
        raise ValueError("Kategorie darf nicht leer sein.")

    if name.isdigit():
        try:
            return Category.objects.get(pk=int(name))
        except Category.DoesNotExist:
            pass

    try:
        return Category.objects.get(name__iexact=name)
    except Category.DoesNotExist:
        available = ', '.join(Category.objects.order_by('name').values_list('name', flat=True))
        raise ValueError(
            f"Kategorie '{name}' nicht gefunden. Verfügbare Kategorien: {available}"
        )


def resolve_client(name: str) -> Client:
    name = (name or '').strip()
    if not name:
        raise ValueError("Kunde darf nicht leer sein.")
    try:
        return Client.objects.get(name__iexact=name)
    except Client.DoesNotExist:
        available = ', '.join(Client.objects.order_by('name').values_list('name', flat=True))
        raise ValueError(
            f"Kunde '{name}' nicht gefunden. Verfügbare Kunden: {available}"
        )
