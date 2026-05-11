from django.contrib import admin
from .models import AlertConfig, Alert


@admin.register(AlertConfig)
class AlertConfigAdmin(admin.ModelAdmin):
    list_display = ['days_before_due', 'liquidity_threshold', 'alert_due_enabled',
                    'alert_overdue_enabled', 'alert_liquidity_enabled']

    def has_add_permission(self, request):
        # Only one instance allowed (Singleton)
        return not AlertConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of the singleton instance
        return False


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['alert_type', 'booking', 'mail_sent', 'created_at']
    list_filter = ['alert_type', 'mail_sent', 'created_at']
    search_fields = ['message', 'dedup_key']
    readonly_fields = ['created_at', 'dedup_key']
