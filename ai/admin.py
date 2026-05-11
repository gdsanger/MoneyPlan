"""Django admin configuration for AI app."""
from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from .models import AIConfig, AIRequestLog


@admin.register(AIConfig)
class AIConfigAdmin(admin.ModelAdmin):
    """Admin for AIConfig singleton."""
    list_display = ['provider', 'enabled', 'max_tokens']
    fieldsets = (
        ('Provider-Auswahl', {
            'fields': ('provider', 'enabled', 'max_tokens'),
        }),
        ('OpenAI', {
            'fields': ('openai_api_key', 'openai_model'),
            'classes': ('collapse',),
        }),
        ('Anthropic', {
            'fields': ('anthropic_api_key', 'anthropic_model'),
            'classes': ('collapse',),
        }),
    )

    def has_add_permission(self, request):
        """Only one instance allowed (Singleton)."""
        return not AIConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of the singleton instance."""
        return False

    def save_model(self, request, obj, form, change):
        """Save the model and test connection."""
        super().save_model(request, obj, form, change)

        # Test connection after saving
        if obj.enabled:
            from ai.service import get_provider
            from ai.exceptions import AIProviderNotConfigured, AIProviderUnavailable

            try:
                provider = get_provider()
                if provider.test_connection():
                    messages.success(request, "✓ Verbindung zum KI-Provider erfolgreich getestet")
                else:
                    messages.warning(request, "⚠ Verbindungstest fehlgeschlagen. Bitte API-Key überprüfen.")
            except AIProviderNotConfigured as e:
                messages.warning(request, f"⚠ {str(e)}")
            except AIProviderUnavailable as e:
                messages.error(request, f"✗ {str(e)}")


@admin.register(AIRequestLog)
class AIRequestLogAdmin(admin.ModelAdmin):
    """Admin for AIRequestLog (read-only)."""
    list_display = ['created_at', 'provider', 'model', 'feature',
                    'input_tokens', 'output_tokens', 'success_icon', 'duration_ms']
    list_filter = ['success', 'provider', 'feature', 'created_at']
    search_fields = ['feature', 'error_message']
    readonly_fields = ['provider', 'model', 'feature', 'input_tokens', 'output_tokens',
                       'success', 'error_message', 'duration_ms', 'created_at']
    date_hierarchy = 'created_at'

    def success_icon(self, obj):
        """Display success/failure icon."""
        if obj.success:
            return format_html('<span style="color: green;">✓</span>')
        else:
            return format_html('<span style="color: red;">✗</span>')
    success_icon.short_description = 'Status'

    def has_add_permission(self, request):
        """Logs are created automatically, not manually."""
        return False

    def has_change_permission(self, request, obj=None):
        """Logs are read-only."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion for cleanup."""
        return True

