"""Views for ISARtec expense reimbursements."""
import base64
import magic
from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from ai.exceptions import AIProviderNotConfigured, AIResponseParseError, AIServiceError
from attachments.services import get_attachments_for, handle_upload

from .forms import ExpenseClaimForm, ReimbursementConfigForm
from .mailer import send_submission_mail
from .models import ExpenseClaim, ReimbursementConfig, ReimbursementSubmission
from .pdf_service import generate_submission_pdf
from .receipt_service import recognize_fuel_receipt
from .services import get_forecast_entry, get_pending_claims, get_unreimbursed_total, lock_pending_claims


@login_required
def claim_list(request):
    """List expense claims with summary and filters."""
    status_filter = request.GET.get('status', 'all')
    claims = ExpenseClaim.objects.all()

    if status_filter == 'pending':
        claims = claims.filter(status=ExpenseClaim.STATUS_PENDING)
    elif status_filter == 'submitted':
        claims = claims.filter(status=ExpenseClaim.STATUS_SUBMITTED)
    elif status_filter == 'reimbursed':
        claims = claims.filter(status=ExpenseClaim.STATUS_REIMBURSED)

    pending_count = ExpenseClaim.objects.filter(status=ExpenseClaim.STATUS_PENDING).count()
    config = ReimbursementConfig.get()

    context = {
        'claims': claims,
        'status_filter': status_filter,
        'unreimbursed_total': get_unreimbursed_total(),
        'forecast_entry': get_forecast_entry(),
        'pending_count': pending_count,
        'config_ready': bool(config.employee_name and config.recipient_email),
    }

    if request.htmx:
        return render(request, 'reimbursements/_list.html', context)

    return render(request, 'reimbursements/list.html', context)


@login_required
def receipt_upload(request):
    """Upload and analyze a fuel receipt."""
    if request.method == 'POST':
        if 'receipt_file' not in request.FILES:
            return render(request, 'reimbursements/_receipt_upload.html', {
                'error': 'Keine Datei ausgewählt',
            })

        uploaded_file = request.FILES['receipt_file']
        file_data = uploaded_file.read()
        mime_type = magic.from_buffer(file_data, mime=True)

        allowed_types = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf']
        if mime_type not in allowed_types:
            return render(request, 'reimbursements/_receipt_upload.html', {
                'error': 'Nicht unterstütztes Dateiformat. Unterstützt: PDF, JPG, PNG, WEBP',
            })

        max_size = 10 * 1024 * 1024
        if len(file_data) > max_size:
            return render(request, 'reimbursements/_receipt_upload.html', {
                'error': 'Datei zu groß (max. 10 MB)',
            })

        try:
            result = recognize_fuel_receipt(file_data, mime_type)

            request.session['fuel_receipt_result'] = {
                'date': result.date,
                'description': result.description,
                'amount': str(result.amount),
                'notes': result.notes,
                'confidence': result.confidence,
                'raw_text': result.raw_text,
                'ai_provider': result.ai_provider,
                'ai_model': result.ai_model,
            }
            request.session['fuel_receipt_file_data'] = base64.b64encode(file_data).decode('utf-8')
            request.session['fuel_receipt_file_name'] = uploaded_file.name
            request.session['fuel_receipt_file_mime_type'] = mime_type

            initial_data = {
                'date': result.date if result.date else date.today(),
                'description': result.description,
                'amount': result.amount,
                'notes': result.notes,
            }
            form = ExpenseClaimForm(initial=initial_data)

            return render(request, 'reimbursements/_receipt_form.html', {
                'form': form,
                'receipt_result': result,
            })
        except AIProviderNotConfigured:
            return render(request, 'reimbursements/_receipt_upload.html', {
                'error': 'KI nicht konfiguriert — bitte API-Key in den Einstellungen hinterlegen',
            })
        except (AIServiceError, AIResponseParseError, ValueError) as e:
            return render(request, 'reimbursements/_receipt_upload.html', {
                'error': f'Analyse fehlgeschlagen: {e}',
            })

    return render(request, 'reimbursements/_receipt_upload.html')


@login_required
def receipt_confirm(request):
    """Save analyzed fuel receipt as ExpenseClaim with attachment."""
    if request.method != 'POST':
        return HttpResponse(status=405)

    if 'fuel_receipt_result' not in request.session or 'fuel_receipt_file_data' not in request.session:
        return render(request, 'reimbursements/_receipt_upload.html', {
            'error': 'Session abgelaufen. Bitte Beleg erneut hochladen.',
        })

    form = ExpenseClaimForm(request.POST)
    receipt_result_data = request.session.get('fuel_receipt_result')

    if not form.is_valid():
        receipt_obj = type('obj', (object,), receipt_result_data)()
        return render(request, 'reimbursements/_receipt_form.html', {
            'form': form,
            'receipt_result': receipt_obj,
        })

    file_data = base64.b64decode(request.session['fuel_receipt_file_data'])
    file_name = request.session['fuel_receipt_file_name']
    mime_type = request.session['fuel_receipt_file_mime_type']

    file_obj = InMemoryUploadedFile(
        file=BytesIO(file_data),
        field_name='file',
        name=file_name,
        content_type=mime_type,
        size=len(file_data),
        charset=None,
    )

    receipt_obj = type('obj', (object,), receipt_result_data)()
    try:
        with transaction.atomic():
            claim = form.save(commit=False)
            claim.status = ExpenseClaim.STATUS_PENDING
            claim.ai_confidence = receipt_result_data.get('confidence', {})
            claim.ai_raw_text = receipt_result_data.get('raw_text', '')
            claim.save()
            handle_upload(file_obj, claim)
    except ValidationError as e:
        error_message = '; '.join(e.messages)
        return render(request, 'reimbursements/_receipt_form.html', {
            'form': form,
            'receipt_result': receipt_obj,
            'upload_error': error_message,
        })
    except Exception as e:
        return render(request, 'reimbursements/_receipt_form.html', {
            'form': form,
            'receipt_result': receipt_obj,
            'upload_error': f'Anhang konnte nicht gespeichert werden: {e}',
        })

    for key in ('fuel_receipt_result', 'fuel_receipt_file_data', 'fuel_receipt_file_name', 'fuel_receipt_file_mime_type'):
        request.session.pop(key, None)

    if request.htmx:
        response = HttpResponse(status=204)
        response['HX-Redirect'] = reverse('reimbursements:list')
        return response

    messages.success(request, 'Tankbeleg gespeichert.')
    return redirect('reimbursements:list')


@login_required
def claim_edit(request, claim_id):
    """Edit an expense claim."""
    claim = get_object_or_404(ExpenseClaim, pk=claim_id)

    if request.method == 'POST':
        form = ExpenseClaimForm(request.POST, instance=claim)
        if form.is_valid():
            form.save()
            if request.htmx:
                response = HttpResponse(status=204)
                response['HX-Redirect'] = reverse('reimbursements:list')
                return response
            return redirect('reimbursements:list')
    else:
        form = ExpenseClaimForm(instance=claim)

    context = {'form': form, 'claim': claim}
    if request.htmx:
        return render(request, 'reimbursements/_form.html', context)
    return render(request, 'reimbursements/form.html', context)


@login_required
def claim_delete(request, claim_id):
    """Delete an expense claim."""
    claim = get_object_or_404(ExpenseClaim, pk=claim_id)
    if request.method == 'POST':
        claim.delete()
        if request.htmx:
            response = HttpResponse(status=204)
            response['HX-Redirect'] = reverse('reimbursements:list')
            return response
        return redirect('reimbursements:list')
    return redirect('reimbursements:list')


@login_required
def claim_toggle_reimbursed(request, claim_id):
    """Toggle reimbursed status (HTMX)."""
    claim = get_object_or_404(ExpenseClaim, pk=claim_id)

    if request.method != 'POST':
        return HttpResponse(status=400)

    if claim.status == ExpenseClaim.STATUS_REIMBURSED:
        claim.status = ExpenseClaim.STATUS_SUBMITTED if claim.submitted_at else ExpenseClaim.STATUS_PENDING
        claim.reimbursed_at = None
    else:
        claim.status = ExpenseClaim.STATUS_REIMBURSED
        claim.reimbursed_at = timezone.now()

    claim.save()
    attachments = get_attachments_for(claim)
    return render(request, 'reimbursements/_row.html', {
        'claim': claim,
        'has_attachment': attachments.exists(),
    })


@login_required
def pdf_preview(request):
    """Generate and download/preview the combined submission PDF."""
    claims = list(get_pending_claims())
    if not claims:
        messages.error(request, 'Keine offenen Belege für die PDF-Vorschau.')
        return redirect('reimbursements:list')

    try:
        pdf_bytes, filename = generate_submission_pdf(claims)
    except Exception as e:
        messages.error(request, f'PDF-Generierung fehlgeschlagen: {e}')
        return redirect('reimbursements:list')

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
def submit_claims(request):
    """Generate PDF, send email, and mark claims as submitted."""
    if request.method != 'POST':
        return HttpResponse(status=405)

    config = ReimbursementConfig.get()
    if not config.recipient_email:
        messages.error(request, 'Bitte Empfänger-E-Mail in den Auslagen-Einstellungen hinterlegen.')
        return redirect('reimbursements:settings')

    try:
        with transaction.atomic():
            claims = lock_pending_claims()
            if not claims:
                messages.error(request, 'Keine offenen Belege zum Einreichen.')
                return redirect('reimbursements:list')

            total_amount = sum((c.amount for c in claims), Decimal('0.00'))
            date_from = min(c.date for c in claims)
            date_to = max(c.date for c in claims)

            now = timezone.now()
            claim_ids = [claim.id for claim in claims]
            ExpenseClaim.objects.filter(id__in=claim_ids).update(
                status=ExpenseClaim.STATUS_SUBMITTED,
                submitted_at=now,
                updated_at=now,
            )

            pdf_bytes, filename = generate_submission_pdf(claims)

            submission = ReimbursementSubmission.objects.create(total_amount=total_amount)
            submission.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)
            submission.claims.set(claims)
    except Exception as e:
        messages.error(request, f'Einreichung konnte nicht gespeichert werden: {e}')
        return redirect('reimbursements:list')

    success, mail_message = send_submission_mail(
        pdf_bytes=pdf_bytes,
        filename=filename,
        claim_count=len(claims),
        total_amount=total_amount,
        date_from=date_from,
        date_to=date_to,
    )

    if not success:
        messages.error(
            request,
            f'Belege wurden als eingereicht gespeichert, aber die E-Mail konnte nicht gesendet werden: {mail_message}',
        )
        return redirect('reimbursements:list')

    messages.success(request, mail_message)
    return redirect('reimbursements:list')


@login_required
def settings_view(request):
    """Edit reimbursement configuration."""
    config = ReimbursementConfig.get()

    if request.method == 'POST':
        form = ReimbursementConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Einstellungen gespeichert.')
            if request.htmx:
                return HttpResponse('<div class="alert alert-success">Einstellungen gespeichert.</div>')
            return redirect('reimbursements:settings')
    else:
        form = ReimbursementConfigForm(instance=config)

    if request.htmx:
        return render(request, 'reimbursements/_settings_form.html', {'form': form})

    return render(request, 'reimbursements/settings.html', {'form': form, 'config': config})
