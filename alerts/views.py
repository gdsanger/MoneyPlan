from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from .models import Alert, AlertConfig
from .forms import AlertConfigForm
import smtplib
from email.mime.text import MIMEText


@login_required
def alert_list(request):
    """Liste aller Alerts"""
    alerts = Alert.objects.all()
    return render(request, 'alerts/alert_list.html', {'alerts': alerts})


@login_required
def alert_settings(request):
    """Alert-Konfiguration bearbeiten"""
    config = AlertConfig.get()

    if request.method == 'POST':
        form = AlertConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Einstellungen erfolgreich gespeichert.')

            # For HTMX requests, return success message
            if request.htmx:
                return HttpResponse('<div class="alert alert-success">Einstellungen erfolgreich gespeichert.</div>')

            return redirect('alerts:settings')
    else:
        form = AlertConfigForm(instance=config)

    # For HTMX requests, return only the form
    if request.htmx:
        return render(request, 'alerts/_settings_form.html', {'form': form})

    return render(request, 'alerts/settings.html', {'form': form, 'config': config})


@login_required
def test_mail(request):
    """Test-Mail senden"""
    if request.method != 'POST':
        return HttpResponse('<div class="alert alert-danger">Ungültige Anfrage.</div>', status=400)

    config = AlertConfig.get()

    # Check if SMTP is configured
    if not config.smtp_host or not config.alert_email:
        return HttpResponse(
            '<div class="alert alert-warning">SMTP-Konfiguration unvollständig. Bitte Host und Empfänger-Adresse angeben.</div>'
        )

    try:
        # Create test message
        msg = MIMEText('Dies ist eine Test-E-Mail von MoneyPlan.')
        msg['Subject'] = 'MoneyPlan Test-Mail'
        msg['From'] = config.smtp_from or 'noreply@moneyplan.local'
        msg['To'] = config.alert_email

        # Send email
        if config.smtp_tls:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10)
            server.starttls()
        else:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10)

        if config.smtp_user and config.smtp_password:
            server.login(config.smtp_user, config.smtp_password)

        server.send_message(msg)
        server.quit()

        return HttpResponse(
            f'<div class="alert alert-success">Test-Mail erfolgreich an {config.alert_email} gesendet!</div>'
        )

    except smtplib.SMTPAuthenticationError:
        return HttpResponse(
            '<div class="alert alert-danger">SMTP-Authentifizierung fehlgeschlagen. Bitte Benutzername und Passwort überprüfen.</div>'
        )
    except smtplib.SMTPException as e:
        return HttpResponse(
            f'<div class="alert alert-danger">SMTP-Fehler: {str(e)}</div>'
        )
    except Exception as e:
        return HttpResponse(
            f'<div class="alert alert-danger">Fehler beim Senden der Test-Mail: {str(e)}</div>'
        )
