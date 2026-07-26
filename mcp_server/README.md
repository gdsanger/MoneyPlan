# MCP-Server für MoneyPlan

Stellt MoneyPlan-Daten (Buchungen, Zeiterfassung, Serienbuchungen) über das
[Model Context Protocol](https://modelcontextprotocol.io) bereit, sodass
KI-Agenten (Claude, OpenAI, ...) direkt damit arbeiten können.

- **Transport:** Streamable HTTP (`/mcp`), kein stdio, kein SSH.
- **Auth:** statischer Token, per `?token=...` (Query-String) **oder**
  `Authorization: Bearer ...`-Header.
- **Prozess:** läuft dauerhaft als eigener Prozess neben Gunicorn/Django, da
  Streamable HTTP/SSE einen durchgehenden ASGI-Event-Loop braucht.

## Tools

| Tool | Zweck |
|---|---|
| `create_booking` | Neue Buchung anlegen (geplant oder gebucht), optional mit `tags` |
| `list_planned_bookings` | Nur geplante Buchungen lesen (nie gebuchte), filterbar nach `tag`/`tag_kind` |
| `list_due_bookings` | Fällige (`due_soon`) und überfällige (`overdue`) geplante Buchungen lesen, filterbar nach `tag`/`tag_kind` |
| `list_categories` | Kategorien auflisten (zur Namens-Auflösung) |
| `list_clients` | Kunden auflisten (zur Namens-Auflösung) |
| `list_tags` | Tags auflisten inkl. Dimension (`kind`) und Farbe (zur Namens-Auflösung) |
| `set_booking_tags` / `set_time_entry_tags` | Tag-Zuordnung einer Buchung/eines Zeiteintrags nachträglich ersetzen |
| `list_time_entries` / `create_time_entry` / `update_time_entry` | Zeiterfassung lesen/anlegen/ändern, `create_time_entry` optional mit `tags`, `list_time_entries` filterbar nach `tag`/`tag_kind` |
| `list_recurring_series` / `create_recurring_series` | Serienbuchungen lesen/neu anlegen |

Kategorien und Kunden werden einheitlich per eindeutigem **Namen**
referenziert (nicht per ID) — beide Felder sind in der Datenbank `unique`.
Ist ein Name unbekannt, listet die Fehlermeldung die verfügbaren Namen auf.

Tags sind nur *innerhalb ihrer Dimension* (`kind`, z.B. `projekt`/`kunde`/
`kostenstelle`/`sonstiges`) eindeutig benannt. Ein Tag-Name wird deshalb per
Namen aufgelöst, solange er in genau einer Dimension vorkommt — kommt derselbe
Name in mehreren Dimensionen vor, verlangt die Fehlermeldung die Tag-ID (aus
`list_tags`) statt des Namens. Tags werden ausschließlich im UI angelegt und
gepflegt; die MCP-Tools ordnen nur bestehende Tags zu.

## Einrichtung

1. **Token erzeugen** und in der Umgebung (`.env` bzw. Systemd-Unit) setzen:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   export MCP_ACCESS_TOKEN="<erzeugter-token>"
   ```

   Weitere Umgebungsvariablen (optional, siehe `config/settings.py`):
   - `MCP_SERVER_HOST` (Default `127.0.0.1`)
   - `MCP_SERVER_PORT` (Default `8800`)
   - `MCP_REQUIRE_HTTPS` (Default: `True` außer bei `DEBUG=True`)

2. **Server starten:**

   ```bash
   source venv/bin/activate
   python manage.py mcp_serve
   ```

   Für die lokale Entwicklung ohne TLS-Reverse-Proxy zusätzlich
   `MCP_REQUIRE_HTTPS=False` setzen.

3. **nginx** vor den Server schalten (TLS-Terminierung, Query-String nicht
   loggen, `Cache-Control: no-store`) — siehe
   [`deploy/nginx-mcp.conf.example`](../deploy/nginx-mcp.conf.example).

4. **Als Custom Connector in Claude Desktop registrieren:**
   - Einstellungen → Connectors → "Add custom connector"
   - URL: `https://mp.angerlabs.de/mcp/?token=<dein-token>`

   Für Clients, die einen `Authorization`-Header setzen können (Claude Code,
   `mcp-remote`-Bridge, eigene Skripte), kann der Token stattdessen als
   `Authorization: Bearer <dein-token>`-Header übergeben werden — das ist der
   bevorzugte Weg, da der Token dann nicht im Query-String/Server-Log auftaucht.

## Token-Rotation

Der Token ist rein konfigurationsbasiert (kein Hardcoding). Rotieren: neuen
Token erzeugen, `MCP_ACCESS_TOKEN` in der Umgebung aktualisieren, Prozess neu
starten, Connector-URL im Client anpassen.

## Tests

```bash
python manage.py test mcp_server
```

Deckt Happy-Path und Fehlerfälle je Tool sowie Auth (gültiger/ungültiger/
fehlender Token, Header vs. Query-String, HTTPS-Pflicht) ab.
