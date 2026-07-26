"""
Uniform name-based resolution for MCP tool inputs.

Category and Client are both referenced by their unique, human-readable
`name` field rather than by database id — MCP clients (AI agents) don't know
internal ids, and both models already enforce uniqueness on name.
"""
from bookings.models import Category
from tags.models import Tag
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


def resolve_client(name) -> Client:
    """Resolve a Client by name (case-insensitive) or numeric id.

    Mirrors resolve_category: accepts both, since some tools surface a
    client id in prior results (e.g. list_time_entries) that callers may
    want to pass straight back in.
    """
    if isinstance(name, int):
        try:
            return Client.objects.get(pk=name)
        except Client.DoesNotExist:
            raise ValueError(f"Kunde mit ID {name} nicht gefunden.")

    name = (name or '').strip()
    if not name:
        raise ValueError("Kunde darf nicht leer sein.")

    if name.isdigit():
        try:
            return Client.objects.get(pk=int(name))
        except Client.DoesNotExist:
            pass

    try:
        return Client.objects.get(name__iexact=name)
    except Client.DoesNotExist:
        available = ', '.join(Client.objects.order_by('name').values_list('name', flat=True))
        raise ValueError(
            f"Kunde '{name}' nicht gefunden. Verfügbare Kunden: {available}"
        )


def resolve_tag(value, include_archived=False) -> Tag:
    """Resolve a Tag by name (case-insensitive) or numeric id.

    Unlike Category/Client, Tag.name is only unique per dimension (`kind`),
    not globally — a bare name can therefore match tags in several
    dimensions. In that case an id (see list_tags) is required instead of a
    name, since there is no single correct dimension to prefer.

    include_archived: when False (default, used when *assigning* a tag),
    archived tags are excluded — mirrors the web UI, which only lets new
    assignments pick non-archived tags. Pass True when *filtering* by tag,
    since already-tagged items should stay findable even if the tag was
    archived afterwards.
    """
    if isinstance(value, int):
        try:
            tag = Tag.objects.get(pk=value)
        except Tag.DoesNotExist:
            raise ValueError(f"Tag mit ID {value} nicht gefunden.")
        if not include_archived and tag.archived:
            raise ValueError(f"Tag '{tag.name}' ist archiviert und kann nicht neu zugeordnet werden.")
        return tag

    value = (value or '').strip()
    if not value:
        raise ValueError("Tag darf nicht leer sein.")

    if value.isdigit():
        try:
            tag = Tag.objects.get(pk=int(value))
        except Tag.DoesNotExist:
            tag = None
        if tag is not None:
            if not include_archived and tag.archived:
                raise ValueError(f"Tag '{tag.name}' ist archiviert und kann nicht neu zugeordnet werden.")
            return tag

    qs = Tag.objects.filter(name__iexact=value)
    if not include_archived:
        qs = qs.filter(archived=False)
    matches = list(qs)

    if not matches:
        available = ', '.join(
            f"{t.name} ({t.get_kind_display()})" for t in Tag.objects.order_by('kind', 'name')
        )
        raise ValueError(f"Tag '{value}' nicht gefunden. Verfügbare Tags: {available}")

    if len(matches) > 1:
        dimensions = ', '.join(sorted(t.get_kind_display() for t in matches))
        raise ValueError(
            f"Tag '{value}' ist nicht eindeutig, vorhanden in mehreren Dimensionen "
            f"({dimensions}). Bitte die Tag-ID verwenden (siehe list_tags)."
        )

    return matches[0]


def resolve_tags(values, include_archived=False) -> list:
    """Resolve a list of tag names/ids (see resolve_tag) to Tag instances.

    Deduplicates by id so passing the same tag twice (e.g. by name and id)
    doesn't raise a duplicate-M2M-entry error further down.
    """
    if values is None:
        return []
    if not isinstance(values, (list, tuple)):
        raise ValueError("'tags' muss eine Liste von Namen oder IDs sein.")

    tags = []
    seen_ids = set()
    for value in values:
        tag = resolve_tag(value, include_archived=include_archived)
        if tag.id not in seen_ids:
            seen_ids.add(tag.id)
            tags.append(tag)
    return tags
