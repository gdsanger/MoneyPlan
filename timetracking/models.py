from django.db import models


class Client(models.Model):
    """Simple client list for grouping time entries."""
    name = models.CharField(max_length=255, unique=True, verbose_name="Name")
    notes = models.TextField(blank=True, verbose_name="Notizen")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")

    class Meta:
        ordering = ['name']
        verbose_name = 'Kunde'
        verbose_name_plural = 'Kunden'

    def __str__(self):
        return self.name


class TimeEntry(models.Model):
    """Time entry for tracking billable hours."""
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name='entries',
        verbose_name="Kunde"
    )
    date = models.DateField(verbose_name="Datum")
    duration = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Dauer (h)",
        help_text="Stunden als Dezimalzahl: 1.5 = 1h 30min, 0.5 = 30min"
    )
    hourly_rate = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name="Stundensatz"
    )
    description = models.CharField(max_length=255, verbose_name="Beschreibung")
    notes = models.TextField(blank=True, verbose_name="Notizen")
    billed = models.BooleanField(default=False, verbose_name="Abgerechnet")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Zeiteintrag'
        verbose_name_plural = 'Zeiteinträge'

    def __str__(self):
        return f"{self.date} | {self.client} | {self.duration}h"

    @property
    def amount(self):
        """Calculated: duration × hourly_rate"""
        return self.duration * self.hourly_rate

    @property
    def duration_display(self):
        """Human readable: 1.5 → '1h 30min', 0.75 → '45min'"""
        hours = int(self.duration)
        minutes = int((self.duration - hours) * 60)
        if hours and minutes:
            return f"{hours}h {minutes}min"
        elif hours:
            return f"{hours}h"
        else:
            return f"{minutes}min"
