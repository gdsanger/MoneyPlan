# MoneyPlan – Claude Code Guidance

## Git Workflow

Always work on a feature branch — never commit directly to `main`.

```bash
git checkout -b cursor/<short-description>
# or
git checkout -b feature/<short-description>
```

Push the branch and open a PR against `main` on `gdsanger/MoneyPlan` when done.

## Tech Stack

- **Backend:** Django 5.x, SQLite (db.sqlite3)
- **Frontend:** Bootstrap 5.3 (dark theme), Bootstrap Icons, HTMX 1.9, Chart.js 4.x
- **Forms:** django-crispy-forms + crispy-bootstrap5
- **AI:** OpenAI + Anthropic (switchable providers in `ai/providers/`)
- **PDF:** WeasyPrint, pdf2image, pypdf, img2pdf
- **Deployment:** Gunicorn + WhiteNoise, hosted at `mp.angerlabs.de`

## Django Apps

| App | Purpose |
|---|---|
| `bookings` | Buchungen, Kategorien, Serien, Verbindlichkeiten, Vermögen |
| `dashboard` | Übersichtsseiten (Index, Jahresübersicht), Context Processors |
| `alerts` | Fälligkeiten und Alert-System |
| `tasks` | Aufgabenverwaltung |
| `timetracking` | Zeiterfassung |
| `reimbursements` | Auslagenabrechnung (inkl. PDF-Export) |
| `attachments` | Dateianhänge (mit python-magic MIME-Prüfung) |
| `ai` | KI-Integration (OpenAI/Anthropic), Einstellungen |

## Common Commands

```bash
# Activate virtualenv (required for all commands)
source venv/bin/activate

# Dev server (Port 8000)
python manage.py runserver

# Tests
python manage.py test

# Tests for a specific app
python manage.py test bookings

# Migrations
python manage.py makemigrations
python manage.py migrate

# Static files
python manage.py collectstatic
```

## Templates

All templates extend `templates/base.html`. Navbar, Alert-Banner und Bootstrap JS sind dort definiert.

HTMX-Requests erkennen: `{% if not request.htmx %}` — Navbar und Container werden bei HTMX-Requests nicht gerendert.

## Context Processors

`dashboard/context_processors.py` stellt global bereit:
- `active_alerts_count` — Anzahl offener Alerts
- `has_critical_alerts` — bool für kritische Alerts (overdue/liquidity)
- `task_badge_count` — Anzahl überfälliger + heute fälliger Aufgaben

## AI Providers

Konfigurierbar über `ai/providers/openai.py` und `ai/providers/anthropic.py`.
Einstellungen über das UI unter `/ai/settings/`.

## Deployment

Produktivserver: `mp.angerlabs.de`
Deploy-Skripte und Patches: `deploy/`
