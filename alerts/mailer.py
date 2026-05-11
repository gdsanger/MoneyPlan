"""
Email sending functionality for alerts.
"""
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .models import Alert, AlertConfig


def send_alert_mail(alert: Alert, config: AlertConfig) -> bool:
    """
    Send HTML mail using SMTP settings from AlertConfig.
    Uses template `templates/mail/alert_{alert.alert_type}.html`.

    Args:
        alert: Alert instance to send
        config: AlertConfig with SMTP settings

    Returns:
        bool: True on success, False on error (logs error, does not raise)
    """
    # Validate SMTP configuration
    if not config.smtp_host or not config.alert_email:
        print("SMTP not configured or no recipient email")
        return False

    # Determine template
    template_name = f"mail/alert_{alert.alert_type}.html"

    try:
        # Build context for template
        context = {
            'alert': alert,
            'booking': alert.booking,
            'config': config,
        }

        # Render HTML content
        html_content = render_to_string(template_name, context)

        # Build subject line
        subject_map = {
            'due_soon': 'Fälligkeitswarnung',
            'overdue': 'Überfällige Buchung',
            'liquidity': 'Liquiditätswarnung'
        }
        subject = subject_map.get(alert.alert_type, 'MoneyPlan Alert')

        # Create email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = config.smtp_from or config.smtp_user
        msg['To'] = config.alert_email

        # Attach HTML content
        html_part = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(html_part)

        # Connect to SMTP server and send
        if config.smtp_tls:
            smtp = smtplib.SMTP(config.smtp_host, config.smtp_port)
            smtp.starttls()
        else:
            smtp = smtplib.SMTP(config.smtp_host, config.smtp_port)

        # Login if credentials provided
        if config.smtp_user and config.smtp_password:
            smtp.login(config.smtp_user, config.smtp_password)

        # Send the email
        smtp.send_message(msg)
        smtp.quit()

        print(f"Alert email sent successfully: {alert.alert_type}")
        return True

    except FileNotFoundError as e:
        print(f"Email template not found: {template_name} - {e}")
        return False
    except smtplib.SMTPException as e:
        print(f"SMTP error sending email: {e}")
        return False
    except Exception as e:
        print(f"Error sending alert email: {e}")
        return False
