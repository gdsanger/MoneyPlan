"""Email sending for expense reimbursement submissions."""
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from alerts.models import AlertConfig
from .models import ReimbursementConfig


def send_submission_mail(
    *,
    pdf_bytes: bytes,
    filename: str,
    claim_count: int,
    total_amount,
    date_from,
    date_to,
) -> tuple[bool, str]:
    """
    Send submission email with a single PDF attachment.

    Returns:
        (success, message)
    """
    alert_config = AlertConfig.get()
    reimbursement_config = ReimbursementConfig.get()

    if not alert_config.smtp_host:
        return False, 'SMTP nicht konfiguriert — bitte Alert-Einstellungen prüfen.'
    if not reimbursement_config.recipient_email:
        return False, 'Empfänger-E-Mail nicht konfiguriert — bitte Auslagen-Einstellungen prüfen.'

    employee = reimbursement_config.employee_name or 'Mitarbeiter'
    subject = f'Auslagenerstattung Tankkosten – {date_to:%m/%Y} – {employee}'

    body_html = f"""<html><body>
<p>Guten Tag,</p>
<p>anbei die Auslagenerstattung für Tankkosten.</p>
<ul>
<li>Anzahl Belege: {claim_count}</li>
<li>Gesamtbetrag: {total_amount:.2f} €</li>
<li>Zeitraum: {date_from:%d.%m.%Y} – {date_to:%d.%m.%Y}</li>
</ul>
<p>Mit freundlichen Grüßen<br>{employee}</p>
</body></html>"""

    try:
        msg = MIMEMultipart('mixed')
        msg['Subject'] = subject
        msg['From'] = alert_config.smtp_from or alert_config.smtp_user
        msg['To'] = reimbursement_config.recipient_email

        msg.attach(MIMEText(body_html, 'html', 'utf-8'))

        attachment = MIMEApplication(pdf_bytes, _subtype='pdf')
        attachment.add_header('Content-Disposition', 'attachment', filename=filename)
        msg.attach(attachment)

        if alert_config.smtp_tls:
            smtp = smtplib.SMTP(alert_config.smtp_host, alert_config.smtp_port, timeout=30)
            smtp.starttls()
        else:
            smtp = smtplib.SMTP(alert_config.smtp_host, alert_config.smtp_port, timeout=30)

        if alert_config.smtp_user and alert_config.smtp_password:
            smtp.login(alert_config.smtp_user, alert_config.smtp_password)

        smtp.send_message(msg)
        smtp.quit()
        return True, f'E-Mail erfolgreich an {reimbursement_config.recipient_email} gesendet.'
    except smtplib.SMTPException as e:
        return False, f'SMTP-Fehler: {e}'
    except Exception as e:
        return False, f'Fehler beim Senden: {e}'
