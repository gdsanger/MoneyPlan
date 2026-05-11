# Finanzplanungs-App — Konsolidiertes Konzept v2.0

**Technologie-Stack:** Python · Django · HTMX · Bootstrap 5 (Dark only)
**Datenbank:** SQLite
**Deployment:** Self-hosted, Linux / macOS x86
**Nutzer:** Single-User mit Django-Auth (Basic Login)

---

## Setup Instructions

### Prerequisites
- Python 3.11 or higher
- pip (Python package manager)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/gdsanger/MoneyPlan.git
cd MoneyPlan
```

2. **Create and activate a virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Run database migrations**
```bash
python manage.py migrate
```

5. **Create a superuser**
```bash
python manage.py createsuperuser
```
Follow the prompts to create your admin account.

6. **Start the development server**
```bash
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000/`

### Cron Setup for Alerts

To enable automated alert checks, add the following cron job (runs daily at 8:00 AM):

```bash
0 8 * * * /path/to/venv/bin/python /path/to/MoneyPlan/manage.py run_alerts
```

Example with full paths:
```bash
0 8 * * * /home/user/MoneyPlan/venv/bin/python /home/user/MoneyPlan/manage.py run_alerts
```

### Environment Variables (Production)

For production deployment, set the following environment variables:

- `SECRET_KEY`: Django secret key (required for production)
- `DEBUG`: Set to `False` for production (default: `True`)

Example:
```bash
export SECRET_KEY='your-secret-key-here'
export DEBUG='False'
```

---

## 1. Datenmodell

### 1.1 Category

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | AutoField PK | |
| `name` | CharField(100) | Eindeutiger Kategoriename |
| `icon` | CharField(50) | Bootstrap-Icon-Name (optional) |
| `color` | CharField(7) | Hex-Farbcode für Charts |

Kategorie-Hierarchie: **flach** (keine Unterkategorien).  
Löschen nur erlaubt, wenn keine Buchungen referenzieren.

---

### 1.2 RecurringSeries (Wiederkehrende Buchungen)

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | AutoField PK | |
| `description` | CharField(255) | Verwendungszweck |
| `amount` | DecimalField(10,2) | Betrag mit Vorzeichen (+/−) |
| `interval` | CharField | `monthly` / `weekly` / `yearly` / `quarterly` |
| `start_date` | DateField | Erste Buchung |
| `end_date` | DateField (null) | Letzte Buchung (optional) |
| `category` | ForeignKey → Category | |
| `notes` | TextField (blank) | Notizen |
| `created_at` | DateTimeField auto | |

Der Wizard erzeugt aus einer `RecurringSeries` eine Menge echter `Booking`-Einträge, die per `series`-FK referenziert sind. Keine virtuellen/generierten Buchungen.

---

### 1.3 Booking (Kernentität)

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | AutoField PK | |
| `date` | DateField | Buchungsdatum (Fälligkeitsdatum) |
| `description` | CharField(255) | Verwendungszweck |
| `amount` | DecimalField(10,2) | **Positiv = Einnahme, Negativ = Ausgabe** |
| `notes` | TextField (blank) | Optionale Notizen |
| `status` | CharField | `planned` / `booked` |
| `category` | ForeignKey → Category | |
| `series` | ForeignKey → RecurringSeries (null) | Referenz auf Ursprungs-Serie |
| `created_at` | DateTimeField auto | |
| `updated_at` | DateTimeField auto | |

**Buchungstyp:** wird ausschließlich über das Vorzeichen des `amount`-Feldes gesteuert.  
Alle Beträge in EUR (kein Währungsfeld).

**Saldoberechnung:** immer automatisch aus den `Booking`-Einträgen — kein gespeicherter Snapshot. Saldovortrag für Monatsansichten wird on-the-fly aus allen Buchungen vor dem Monatsbeginn berechnet.

---

### 1.4 AlertConfig (Singleton)

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | AutoField PK | Immer nur 1 Eintrag |
| `days_before_due` | IntegerField (default: 3) | Vorlaufzeit für Fälligkeits-Alerts |
| `liquidity_threshold` | DecimalField(10,2) | Schwellenwert Liquiditätsengpass (EUR) |
| `alert_due_enabled` | BooleanField | Fälligkeit-Alerts aktiv |
| `alert_overdue_enabled` | BooleanField | Überschreitung-Alerts aktiv |
| `alert_liquidity_enabled` | BooleanField | Liquiditäts-Alerts aktiv |
| `smtp_host` | CharField | |
| `smtp_port` | IntegerField (default: 587) | |
| `smtp_user` | CharField | |
| `smtp_password` | CharField | Verschlüsselt gespeichert |
| `smtp_from` | EmailField | Absenderadresse |
| `smtp_tls` | BooleanField (default: True) | |
| `alert_email` | EmailField | Empfänger-Adresse |

---

### 1.5 Alert

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | AutoField PK | |
| `alert_type` | CharField | `due_soon` / `overdue` / `liquidity` |
| `booking` | ForeignKey → Booking (null) | Referenz-Buchung (bei Liquiditäts-Alert: null) |
| `message` | TextField | Beschreibender Text |
| `mail_sent` | BooleanField | Mail wurde bereits verschickt |
| `created_at` | DateTimeField auto | |
| `dedup_key` | CharField unique | Hash aus `alert_type + booking_id + date` — verhindert Duplikate |

**Alerts werden nicht manuell quittiert.** Sie bleiben in der UI sichtbar, solange die auslösende Bedingung besteht. Der Alert-Check läuft täglich (Cron oder django-apscheduler) und legt neue Alert-Einträge nur an, wenn der `dedup_key` noch nicht existiert.

---

## 2. Projektstruktur

```
finanzapp/
├── config/                  ← Django-Projekt-Settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── bookings/                ← Core-App
│   ├── models.py            ← Booking, Category, RecurringSeries
│   ├── views.py             ← HTMX-Partials + Full-Page Views
│   ├── forms.py
│   ├── urls.py
│   ├── services.py          ← Saldo-Berechnung, Forecast-Logik
│   ├── wizard.py            ← Generator für Serien-Buchungen
│   └── admin.py
│
├── dashboard/               ← KPIs, Charts, Monatsansicht
│   ├── views.py
│   ├── urls.py
│   └── chart_data.py        ← JSON-Endpunkte für Chart.js
│
├── alerts/                  ← Alerting-System
│   ├── models.py            ← Alert, AlertConfig
│   ├── checks.py            ← Alert-Logik (Dedup, Checks)
│   ├── mailer.py            ← SMTP-Versand
│   ├── management/
│   │   └── commands/
│   │       └── run_alerts.py ← python manage.py run_alerts
│   └── urls.py
│
├── templates/
│   ├── base.html            ← Bootstrap 5 Dark, Navbar, Alert-Banner
│   ├── dashboard/
│   ├── bookings/
│   ├── alerts/
│   └── mail/                ← HTML-Mailtemplates (Outlook-kompatibel)
│
├── static/
│   ├── css/custom.css
│   └── js/app.js            ← HTMX-Helpers, Chart.js-Init
│
├── manage.py
└── requirements.txt
```

---

## 3. Django Apps und Zuständigkeiten

### `bookings`
- CRUD für `Booking`, `Category`, `RecurringSeries`
- Wizard-Flow: Formular → Vorschau der zu erzeugenden Buchungen → Bestätigung → Bulk-Create
- Monatsansicht mit Vorwärts/Zurück-Buttons (HTMX-Partial)
- Listenansicht fälliger Buchungen bis Monatsende
- `services.py`: `get_balance()`, `get_monthly_balance(month, year)`, `get_forecast(months=3)`

### `dashboard`
- Dashboard-View: KPI-Karten + Chart.js-Diagramme
- JSON-Endpunkte für Charts (Chart.js fetched via HTMX oder fetch())
- Diagramme: Liniendiagramm Saldoverlauf Ist + Forecast, Balken Top-10-Kategorien, Donut Einnahmen/Ausgaben

### `alerts`
- `checks.py` prüft täglich: Fälligkeit (n Tage vor `date`), überschritten (`date` < heute & `status = planned`), Liquiditätsengpass (projizierter Saldo < Schwellenwert)
- Dedup-Check vor jedem neuen Alert
- `management/commands/run_alerts.py` → Cron-Job: `0 8 * * * python manage.py run_alerts`
- Alternativ: `django-apscheduler` wenn kein Cron verfügbar

---

## 4. UI-Ansichten

| Ansicht | Beschreibung |
|---------|--------------|
| Dashboard | KPIs, Forecast-Chart, Top-Kategorien, Alert-Banner |
| Monatsansicht | Buchungen eines Monats, ◀ ▶ Navigation, Saldovortrag |
| Buchungsliste | Alle Buchungen, filterbar nach Status/Typ/Kategorie |
| Fälligkeitsliste | Geplante Buchungen bis Monatsende |
| Buchung erfassen/bearbeiten | Inline-Form via HTMX |
| Kategorie-Verwaltung | Liste + CRUD (Löschen nur ohne Buchungen) |
| Serien-Wizard | 3-Step: Konfiguration → Vorschau → Bestätigung |
| Serien-Übersicht | Liste aller RecurringSeries, Buchungen je Serie einsehbar |
| Alert-Einstellungen | Schwellenwerte, SMTP-Konfiguration (erfordert Login) |

---

## 5. Dashboard KPIs

| KPI | Definition |
|-----|------------|
| Geldmittel verfügbar | Summe aller `booked`-Buchungen |
| Offene Ausgaben | Summe aller `planned`-Buchungen mit negativem Betrag |
| Offene Einnahmen | Summe aller `planned`-Buchungen mit positivem Betrag |
| Verfügbare Mittel (Monat) | Ist-Saldo + offene Einnahmen − offene Ausgaben im laufenden Monat |
| Verfügbare Mittel (Gesamt) | Ist-Saldo + alle offenen Einnahmen − alle offenen Ausgaben |
| Forecast +3 Monate | Projizierter Saldoverlauf auf Basis geplanter Buchungen |

---

## 6. Forecast-Logik (Step 1)

Forecast basiert ausschließlich auf vorhandenen `planned`-Buchungen mit einem `date` in der Zukunft. Für jeden der nächsten 3 Monate wird der projizierte Saldo berechnet:

```
forecast_saldo(monat) = aktueller_ist_saldo
                       + sum(planned_einnahmen bis monat)
                       − sum(planned_ausgaben bis monat)
```

KI-basierte Mustererkennung ist als Step 2 geplant und nicht Teil dieser Version.

---

## 7. Alerting

### Alert-Typen

| Typ | Trigger | Dedup-Key |
|-----|---------|-----------|
| `due_soon` | `date` liegt in ≤ n Tagen & `status = planned` | `due_soon_{booking_id}_{date}` |
| `overdue` | `date` < heute & `status = planned` | `overdue_{booking_id}` |
| `liquidity` | projizierter Saldo < Schwellenwert (AlertConfig) | `liquidity_{YYYY-MM-DD}` |

### Ablauf

1. `run_alerts` wird täglich per Cron ausgeführt (`0 8 * * * python manage.py run_alerts`)
2. Für jeden Trigger: Dedup-Key berechnen, prüfen ob bereits in `Alert`-Tabelle
3. Wenn neu: Alert-Eintrag anlegen + Mail versenden (falls SMTP konfiguriert)
4. Alerts bleiben sichtbar, bis die auslösende Bedingung nicht mehr zutrifft (kein manuelles Quittieren)

### Mail-Templates

- HTML-Dateien im Filesystem unter `templates/mail/`
- Outlook-kompatibles Table-Layout (kein Flexbox/Grid)
- Angenehme dunkle Farbgebung, aber mit hellem Hintergrund für maximale Mail-Kompatibilität

---

## 8. Technische Abhängigkeiten

```
Django>=4.2
django-htmx
crispy-bootstrap5
django-apscheduler   # optional, falls kein Cron
```

Chart.js wird über CDN eingebunden (kein Build-Step nötig).

---

## 9. Offene Punkte (Step 2)

- KI-Analyse und Mustererkennung im Forecast
- CSV/JSON-Export der Buchungen
- PostgreSQL-Migration falls Multi-User oder höhere Last gewünscht
