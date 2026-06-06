"""Generate combined submission PDF (application + receipts)."""
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from attachments.services import get_attachments_for

from .models import ExpenseClaim, ReimbursementConfig


def claims_missing_receipts(claims: list[ExpenseClaim]) -> list[ExpenseClaim]:
    """Return claims that have no file attachment."""
    return [claim for claim in claims if not get_attachments_for(claim).exists()]


def ensure_claims_have_receipts(claims: list[ExpenseClaim]) -> None:
    """Raise ValueError if any claim is missing a receipt attachment."""
    missing = claims_missing_receipts(claims)
    if not missing:
        return

    descriptions = ', '.join(
        f'{claim.date:%d.%m.%Y} ({claim.description})' for claim in missing
    )
    raise ValueError(f'Folgende Belege haben keinen Anhang: {descriptions}')


def format_euro(amount: Decimal) -> str:
    """Format amount as German currency string."""
    return f'{amount:,.2f} €'.replace(',', 'X').replace('.', ',').replace('X', '.')


def build_submission_filename(submission_date: date | None = None) -> str:
    submission_date = submission_date or timezone.localdate()
    return f'{submission_date:%Y%m%d} ISARtec Auslagenerstattung.pdf'


def generate_application_pdf_bytes(claims: list[ExpenseClaim], config: ReimbursementConfig) -> bytes:
    """Render the ISARtec application form as PDF."""
    total = sum((claim.amount for claim in claims), Decimal('0.00'))
    today = timezone.localdate()

    rows = [
        {
            'cost_type': 'Tanken',
            'label': claim.date.strftime('%d.%m.%Y'),
            'amount': format_euro(claim.amount),
            'notes': claim.notes,
        }
        for claim in claims
    ]

    html = render_to_string('reimbursements/application_pdf.html', {
        'config': config,
        'rows': rows,
        'total': format_euro(total),
        'today': today.strftime('%d.%m.%Y'),
        'logo_path': _logo_file_uri(config),
        'signature_path': _signature_file_uri(config),
    })

    try:
        from weasyprint import HTML
    except ImportError as e:
        raise RuntimeError('weasyprint is required for PDF generation') from e

    return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()


def _media_file_uri(file_field) -> str:
    if file_field and file_field.name:
        path = Path(file_field.path)
        if path.exists():
            return path.as_uri()
    return ''


def _logo_file_uri(config: ReimbursementConfig) -> str:
    uri = _media_file_uri(config.logo)
    if uri:
        return uri

    fallback = Path(settings.BASE_DIR) / 'static' / 'img' / 'isartec-logo.svg'
    if fallback.exists():
        return fallback.as_uri()
    return ''


def _signature_file_uri(config: ReimbursementConfig) -> str:
    return _media_file_uri(config.signature_image)


def _image_to_pdf_bytes(image_bytes: bytes, mime_type: str) -> bytes:
    """Convert image bytes to a single-page PDF."""
    import img2pdf

    if mime_type == 'image/webp':
        from PIL import Image
        buffer = BytesIO()
        with Image.open(BytesIO(image_bytes)) as img:
            rgb = img.convert('RGB')
            rgb.save(buffer, format='JPEG', quality=95)
        image_bytes = buffer.getvalue()

    return img2pdf.convert(image_bytes)


def _append_attachment_pages(writer, claim: ExpenseClaim) -> None:
    """Append receipt file pages for a claim to the PDF writer."""
    from pypdf import PdfReader, PdfWriter

    attachments = get_attachments_for(claim)
    if not attachments:
        raise ValueError(
            f'Beleg vom {claim.date:%d.%m.%Y} ({claim.description}) hat keinen Anhang.'
        )

    attachment = attachments[0]
    attachment.file.open('rb')
    try:
        file_bytes = attachment.file.read()
    finally:
        attachment.file.close()

    mime = attachment.mime_type
    if mime == 'application/pdf':
        reader = PdfReader(BytesIO(file_bytes))
        for page in reader.pages:
            writer.add_page(page)
    elif mime.startswith('image/'):
        image_pdf = _image_to_pdf_bytes(file_bytes, mime)
        reader = PdfReader(BytesIO(image_pdf))
        for page in reader.pages:
            writer.add_page(page)


def generate_submission_pdf(claims: list[ExpenseClaim] | None = None) -> tuple[bytes, str]:
    """
    Build the full submission PDF: application + all receipt attachments.

    Returns:
        (pdf_bytes, filename)
    """
    from pypdf import PdfReader, PdfWriter

    if claims is None:
        from .services import get_pending_claims
        claims = list(get_pending_claims())

    if not claims:
        raise ValueError('Keine offenen Belege zum Einreichen vorhanden.')

    ensure_claims_have_receipts(claims)

    config = ReimbursementConfig.get()
    application_pdf = generate_application_pdf_bytes(claims, config)

    writer = PdfWriter()
    app_reader = PdfReader(BytesIO(application_pdf))
    for page in app_reader.pages:
        writer.add_page(page)

    for claim in claims:
        _append_attachment_pages(writer, claim)

    output = BytesIO()
    writer.write(output)
    filename = build_submission_filename()
    return output.getvalue(), filename
