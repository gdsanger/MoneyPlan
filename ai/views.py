from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from .models import AIConfig
from .forms import AIConfigForm
from .service import get_provider
from .exceptions import AIProviderNotConfigured, AIServiceError


@login_required
def ai_settings(request):
    """AI configuration settings page."""
    config = AIConfig.get()

    if request.method == 'POST':
        form = AIConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'KI-Einstellungen wurden gespeichert.')
            return redirect('ai:settings')
    else:
        form = AIConfigForm(instance=config)

    context = {
        'form': form,
    }

    return render(request, 'ai/settings.html', context)


@login_required
def test_connection(request):
    """Test AI provider connection."""
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        provider = get_provider()
        result = provider.test_connection()

        if result:
            if request.htmx:
                return HttpResponse(
                    '<div class="alert alert-success">'
                    '<i class="bi bi-check-circle-fill"></i> '
                    'Verbindung erfolgreich! Provider ist erreichbar.'
                    '</div>'
                )
            messages.success(request, 'Verbindung erfolgreich!')
        else:
            if request.htmx:
                return HttpResponse(
                    '<div class="alert alert-danger">'
                    '<i class="bi bi-exclamation-triangle-fill"></i> '
                    'Verbindung fehlgeschlagen.'
                    '</div>'
                )
            messages.error(request, 'Verbindung fehlgeschlagen.')

    except AIProviderNotConfigured as e:
        if request.htmx:
            return HttpResponse(
                f'<div class="alert alert-warning">'
                f'<i class="bi bi-exclamation-triangle-fill"></i> '
                f'{str(e)}'
                f'</div>'
            )
        messages.warning(request, str(e))

    except Exception as e:
        if request.htmx:
            return HttpResponse(
                f'<div class="alert alert-danger">'
                f'<i class="bi bi-exclamation-triangle-fill"></i> '
                f'Fehler: {str(e)}'
                f'</div>'
            )
        messages.error(request, f'Fehler: {str(e)}')

    return redirect('ai:settings')
