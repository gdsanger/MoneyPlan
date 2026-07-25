"""
Token-authenticated HTTP API for attachments (used by agents, not the web UI).

Unlike the `login_required` views in `views.py`, these endpoints are meant to
be called with a static access token (curl, MCP-side tooling) instead of a
session cookie, and accept real multipart file uploads instead of the Base64
payloads MCP tools are limited to.
"""
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bookings.models import Booking
from mcp_server.auth import extract_token_from_django_request, token_is_valid

from .services import handle_upload


@csrf_exempt
@require_POST
def upload_booking_attachment(request, booking_id):
    """
    Haengt eine per multipart/form-data hochgeladene Datei (Feld 'file') als
    Anhang an eine Buchung an - fuer Agenten, die groessere Belege nicht durch
    ihren Kontext (Base64) schicken wollen/koennen.

    URL: POST /api/bookings/<booking_id>/attachment/
    Auth: 'Authorization: Bearer <token>' oder '?token=<token>', wie beim
    MCP-Server (settings.MCP_ACCESS_TOKEN).

    curl -F "file=@rechnung.pdf" -H "Authorization: Bearer <token>" \\
        https://mpmcp.angerlabs.de/api/bookings/<booking_id>/attachment/
    """
    if not token_is_valid(extract_token_from_django_request(request)):
        return JsonResponse({'error': 'Invalid or missing token'}, status=401)

    booking = get_object_or_404(Booking, pk=booking_id)

    upload = request.FILES.get('file')
    if not upload:
        return JsonResponse({'error': "Feld 'file' fehlt oder ist leer."}, status=400)

    try:
        attachment = handle_upload(upload, booking)
    except ValidationError as exc:
        message = '; '.join(exc.messages)
        status = 413 if 'zu groß' in message else 400
        return JsonResponse({'error': message}, status=status)

    return JsonResponse({
        'attachment_id': attachment.id,
        'filename': attachment.filename,
        'file_size': attachment.file_size,
        'mime_type': attachment.mime_type,
        'uploaded_at': attachment.uploaded_at.isoformat(),
        'url': attachment.file.url,
    }, status=201)
