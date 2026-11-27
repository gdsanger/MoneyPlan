from decimal import Decimal

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
    tags = models.ManyToManyField(
        'tags.Tag',
        blank=True,
        related_name='time_entries',
        verbose_name="Tags",
    )
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


class MinijobSettings(models.Model):
    """Einstellungen für den Minijob (Singleton, nur Nachweis – keine Prognose)."""
    full_name = models.CharField(max_length=255, blank=True, default='', verbose_name="Name",
                                 help_text="Erscheint auf dem Nachweis (Druck/CSV).")
    employer = models.CharField(max_length=255, blank=True, default='', verbose_name="Arbeitgeber")
    hourly_rate = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('25.00'), verbose_name="Stundensatz (€)"
    )
    monthly_limit = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('300.00'), verbose_name="Monatliche Pauschale (€)",
        help_text="Darüber hinaus geleistete Stunden werden per Rechnung über das Gewerbe abgerechnet."
    )

    class Meta:
        verbose_name = 'Minijob-Einstellungen'
        verbose_name_plural = 'Minijob-Einstellungen'

    def __str__(self):
        return f"Minijob {self.employer}".strip()

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        obj.refresh_from_db()  # Defaults als Decimal aus der DB laden
        return obj

    @property
    def limit_hours(self):
        """Stunden, die durch die Monatspauschale abgedeckt sind."""
        if not self.hourly_rate:
            return Decimal('0')
        return (self.monthly_limit / self.hourly_rate).quantize(Decimal('0.01'))


class MinijobShift(models.Model):
    """Ein Arbeitseinsatz im Minijob (Zeitnachweis)."""
    date = models.DateField(verbose_name="Datum")
    start_time = models.TimeField(verbose_name="Beginn")
    end_time = models.TimeField(verbose_name="Ende")
    break_minutes = models.PositiveIntegerField(default=0, verbose_name="Pause (min)")
    notes = models.CharField(max_length=255, blank=True, verbose_name="Tätigkeit / Notiz")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")

    class Meta:
        ordering = ['-date', '-start_time']
        verbose_name = 'Minijob-Einsatz'
        verbose_name_plural = 'Minijob-Einsätze'

    def __str__(self):
        return f"{self.date} {self.start_time:%H:%M}-{self.end_time:%H:%M}"

    @property
    def minutes(self):
        start = self.start_time.hour * 60 + self.start_time.minute
        end = self.end_time.hour * 60 + self.end_time.minute
        if end <= start:  # über Mitternacht
            end += 24 * 60
        return max(end - start - self.break_minutes, 0)

    @property
    def hours(self):
        return (Decimal(self.minutes) / 60).quantize(Decimal('0.01'))

    @property
    def duration_display(self):
        h, m = divmod(self.minutes, 60)
        return f"{h}h {m:02d}min" if h else f"{m}min"
