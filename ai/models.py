"""AI service models."""
from django.db import models


PROVIDER_CHOICES = [
    ('openai', 'OpenAI'),
    ('anthropic', 'Anthropic'),
]


class AIConfig(models.Model):
    """Singleton configuration for AI service."""
    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default='anthropic',
        verbose_name='KI-Provider'
    )

    # OpenAI
    openai_api_key = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='OpenAI API Key'
    )
    openai_model = models.CharField(
        max_length=100,
        default='gpt-4o-mini',
        verbose_name='OpenAI Model'
    )

    # Anthropic
    anthropic_api_key = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Anthropic API Key'
    )
    anthropic_model = models.CharField(
        max_length=100,
        default='claude-3-5-haiku-20241022',
        verbose_name='Anthropic Model'
    )

    # General
    max_tokens = models.IntegerField(
        default=1000,
        verbose_name='Max Tokens'
    )
    enabled = models.BooleanField(
        default=True,
        verbose_name='KI-Service aktiviert'
    )

    class Meta:
        verbose_name = 'KI-Konfiguration'
        verbose_name_plural = 'KI-Konfiguration'

    def __str__(self):
        return 'KI-Konfiguration'

    def save(self, *args, **kwargs):
        """Ensure only one instance exists (Singleton)."""
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        """Get or create the singleton instance."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AIRequestLog(models.Model):
    """Audit trail for AI requests (no sensitive data)."""
    provider = models.CharField(
        max_length=20,
        verbose_name='Provider'
    )
    model = models.CharField(
        max_length=100,
        verbose_name='Model'
    )
    feature = models.CharField(
        max_length=50,
        verbose_name='Feature'
    )
    input_tokens = models.IntegerField(
        default=0,
        verbose_name='Input Tokens'
    )
    output_tokens = models.IntegerField(
        default=0,
        verbose_name='Output Tokens'
    )
    success = models.BooleanField(
        verbose_name='Erfolgreich'
    )
    error_message = models.TextField(
        blank=True,
        verbose_name='Fehlermeldung'
    )
    duration_ms = models.IntegerField(
        default=0,
        verbose_name='Dauer (ms)'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Erstellt am'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'KI-Anfrage Log'
        verbose_name_plural = 'KI-Anfrage Logs'

    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"[{status}] {self.provider} - {self.feature} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
