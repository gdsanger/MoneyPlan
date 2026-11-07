"""PWA-Endpunkte: Web-App-Manifest und minimaler Service Worker.

Bewusst ohne Offline-Funktion – die App ist nur installierbar. Beides wird
vom Root-Pfad ausgeliefert, damit der Service Worker den gesamten Origin
als Scope hat.
"""
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

THEME_COLOR = "#212529"

SERVICE_WORKER_JS = """\
// MoneyPlan Service Worker – nur für die Installierbarkeit (PWA).
// Kein Caching, keine Offline-Unterstützung: alle Requests gehen direkt ans Netz.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
"""


@require_GET
def manifest(request):
    data = {
        "name": "MoneyPlan",
        "short_name": "MoneyPlan",
        "description": "Persönliche Finanzplanung",
        "id": "/",
        "start_url": "/dashboard/",
        "scope": "/",
        "display": "standalone",
        "lang": "de",
        "background_color": THEME_COLOR,
        "theme_color": THEME_COLOR,
        "icons": [
            {"src": "/static/img/pwa/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/static/img/pwa/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/static/img/pwa/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    response = JsonResponse(data, json_dumps_params={"ensure_ascii": False})
    response["Content-Type"] = "application/manifest+json"
    return response


@require_GET
@never_cache
def service_worker(request):
    response = HttpResponse(SERVICE_WORKER_JS, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    return response
