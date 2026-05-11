from django.db import models
from django.utils import timezone


class Category(models.Model):
    """Kategorie für Buchungen"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Name")
    icon = models.CharField(max_length=50, blank=True, verbose_name="Bootstrap Icon")
    color = models.CharField(max_length=7, default="#6c757d", verbose_name="Farbe (Hex)")

    class Meta:
        verbose_name = "Kategorie"
        verbose_name_plural = "Kategorien"
        ordering = ['name']

    def __str__(self):
        return self.name


class RecurringSeries(models.Model):
    """Wiederkehrende Buchungen (Serie)"""
    INTERVAL_CHOICES = [
        ('weekly', 'Wöchentlich'),
        ('monthly', 'Monatlich'),
        ('quarterly', 'Vierteljährlich'),
        ('yearly', 'Jährlich'),
    ]

    description = models.CharField(max_length=255, verbose_name="Beschreibung")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Betrag")
    interval = models.CharField(max_length=20, choices=INTERVAL_CHOICES, verbose_name="Intervall")
    start_date = models.DateField(verbose_name="Startdatum")
    end_date = models.DateField(null=True, blank=True, verbose_name="Enddatum")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='series', verbose_name="Kategorie")
    notes = models.TextField(blank=True, verbose_name="Notizen")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")

    class Meta:
        verbose_name = "Wiederkehrende Serie"
        verbose_name_plural = "Wiederkehrende Serien"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.description} ({self.get_interval_display()})"


class Booking(models.Model):
    """Buchung (Kernentität)"""
    STATUS_CHOICES = [
        ('planned', 'Geplant'),
        ('booked', 'Gebucht'),
    ]

    date = models.DateField(verbose_name="Datum")
    description = models.CharField(max_length=255, verbose_name="Beschreibung")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Betrag")
    notes = models.TextField(blank=True, verbose_name="Notizen")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned', verbose_name="Status")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='bookings', verbose_name="Kategorie")
    series = models.ForeignKey(RecurringSeries, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='bookings', verbose_name="Serie")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        verbose_name = "Buchung"
        verbose_name_plural = "Buchungen"
        ordering = ['date', 'id']

    def __str__(self):
        sign = '+' if self.amount >= 0 else ''
        return f"{self.date} | {self.description} | {sign}{self.amount} €"

    @property
    def is_income(self):
        return self.amount >= 0

    @property
    def is_expense(self):
        return self.amount < 0
