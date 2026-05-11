from django.db import models
from datetime import date, timedelta


PRIORITY_CHOICES = [
    ('low', 'Niedrig'),
    ('medium', 'Mittel'),
    ('high', 'Hoch'),
]

STATUS_CHOICES = [
    ('open', 'Offen'),
    ('done', 'Erledigt'),
]


class Task(models.Model):
    """Aufgabe (Task) für finanzrelevante To-Dos"""

    PRIORITY_ORDER = {
        'high': 1,
        'medium': 2,
        'low': 3,
    }

    title = models.CharField(max_length=255, verbose_name='Titel')
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    due_date = models.DateField(null=True, blank=True, verbose_name='Fälligkeit')
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium',
        verbose_name='Priorität'
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='open',
        verbose_name='Status'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')

    class Meta:
        ordering = ['due_date', 'title']
        verbose_name = 'Aufgabe'
        verbose_name_plural = 'Aufgaben'

    def __str__(self):
        return self.title

    @property
    def priority_order(self):
        """Get numeric priority for ordering (lower is higher priority)"""
        return self.PRIORITY_ORDER.get(self.priority, 999)

    @property
    def is_overdue(self):
        """Check if task is overdue"""
        return self.due_date and self.due_date < date.today() and self.status == 'open'

    @property
    def is_due_soon(self):
        """Check if task is due within the next 3 days"""
        if not self.due_date or self.status != 'open':
            return False
        return date.today() <= self.due_date <= date.today() + timedelta(days=3)
