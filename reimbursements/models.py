from django.db import models


class ReimbursementConfig(models.Model):
    """Singleton configuration for ISARtec expense reimbursements."""
    employee_name = models.CharField(max_length=255, blank=True, verbose_name='Name')
    bank_name = models.CharField(max_length=255, blank=True, verbose_name='Bank')
    iban = models.CharField(max_length=34, blank=True, verbose_name='IBAN')
    bic = models.CharField(max_length=11, blank=True, verbose_name='BIC')
    expense_purpose = models.CharField(
        max_length=255,
        default='Tanken Fahrzeug M-XO 475',
        verbose_name='Grund und Zweck',
    )
    place = models.CharField(max_length=100, default='Landshut', verbose_name='Ort')
    recipient_email = models.EmailField(blank=True, verbose_name='Empfänger E-Mail')

    class Meta:
        verbose_name = 'Auslagen-Konfiguration'
        verbose_name_plural = 'Auslagen-Konfiguration'

    def __str__(self):
        return 'Auslagen-Konfiguration'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ExpenseClaim(models.Model):
    """A fuel receipt awaiting ISARtec reimbursement."""
    STATUS_PENDING = 'pending'
    STATUS_SUBMITTED = 'submitted'
    STATUS_REIMBURSED = 'reimbursed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Offen'),
        (STATUS_SUBMITTED, 'Eingereicht'),
        (STATUS_REIMBURSED, 'Erstattet'),
    ]

    date = models.DateField(verbose_name='Datum')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Betrag')
    description = models.CharField(max_length=255, verbose_name='Beschreibung')
    notes = models.TextField(blank=True, verbose_name='Notizen')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name='Status',
    )
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name='Eingereicht am')
    reimbursed_at = models.DateTimeField(null=True, blank=True, verbose_name='Erstattet am')
    ai_confidence = models.JSONField(default=dict, blank=True, verbose_name='KI-Konfidenz')
    ai_raw_text = models.TextField(blank=True, verbose_name='KI-Rohtext')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Auslage'
        verbose_name_plural = 'Auslagen'

    def __str__(self):
        return f'{self.date} | {self.description} | {self.amount} €'

    @property
    def is_unreimbursed(self):
        return self.status != self.STATUS_REIMBURSED


class ReimbursementSubmission(models.Model):
    """Archived submission package sent to accounting."""
    claims = models.ManyToManyField(ExpenseClaim, related_name='submissions', verbose_name='Belege')
    pdf_file = models.FileField(upload_to='uploads/reimbursements/submissions/', verbose_name='PDF')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Gesamtbetrag')
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name='Eingereicht am')

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Einreichung'
        verbose_name_plural = 'Einreichungen'

    def __str__(self):
        return f'Einreichung {self.submitted_at:%d.%m.%Y} — {self.total_amount} €'
