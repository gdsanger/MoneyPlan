from django.db import models
from bookings.models import Booking


class AlertConfig(models.Model):
    """Singleton-Konfiguration für Alerts"""
    days_before_due = models.IntegerField(default=3, verbose_name="Tage vor Fälligkeit")
    liquidity_threshold = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Liquiditätsschwelle (EUR)")
    alert_due_enabled = models.BooleanField(default=True, verbose_name="Fälligkeits-Alerts aktiv")
    alert_overdue_enabled = models.BooleanField(default=True, verbose_name="Überschreitungs-Alerts aktiv")
    alert_liquidity_enabled = models.BooleanField(default=True, verbose_name="Liquiditäts-Alerts aktiv")

    smtp_host = models.CharField(max_length=255, blank=True, verbose_name="SMTP Host")
    smtp_port = models.IntegerField(default=587, verbose_name="SMTP Port")
    smtp_user = models.CharField(max_length=255, blank=True, verbose_name="SMTP Benutzer")
    smtp_password = models.CharField(max_length=255, blank=True, verbose_name="SMTP Passwort")
    smtp_from = models.EmailField(blank=True, verbose_name="Absenderadresse")
    smtp_tls = models.BooleanField(default=True, verbose_name="TLS verwenden")
    alert_email = models.EmailField(blank=True, verbose_name="Empfänger-Adresse")

    class Meta:
        verbose_name = "Alert-Konfiguration"
        verbose_name_plural = "Alert-Konfiguration"

    def __str__(self):
        return "Alert-Konfiguration"

    def save(self, *args, **kwargs):
        # Ensure only one instance exists (Singleton)
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_config(cls):
        config, created = cls.objects.get_or_create(pk=1)
        return config


class Alert(models.Model):
    """Alert-Eintrag"""
    ALERT_TYPE_CHOICES = [
        ('due_soon', 'Fällig in Kürze'),
        ('overdue', 'Überfällig'),
        ('liquidity', 'Liquiditätsengpass'),
    ]

    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES, verbose_name="Alert-Typ")
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, null=True, blank=True,
                                related_name='alerts', verbose_name="Buchung")
    message = models.TextField(verbose_name="Nachricht")
    mail_sent = models.BooleanField(default=False, verbose_name="Mail versendet")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    dedup_key = models.CharField(max_length=255, unique=True, verbose_name="Dedup-Schlüssel")

    class Meta:
        verbose_name = "Alert"
        verbose_name_plural = "Alerts"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.created_at.strftime('%Y-%m-%d')}"
