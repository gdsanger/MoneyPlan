"""Admin configuration for time tracking."""
from django.contrib import admin
from .models import Client, TimeEntry


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """Admin for Client model."""
    list_display = ['name', 'created_at']
    search_fields = ['name']
    ordering = ['name']


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    """Admin for TimeEntry model."""
    list_display = ['date', 'client', 'duration_display', 'hourly_rate', 'amount', 'billed']
    list_filter = ['billed', 'client', 'date']
    list_editable = ['billed']
    search_fields = ['description', 'client__name']
    date_hierarchy = 'date'
    ordering = ['-date', '-created_at']

    def amount(self, obj):
        """Display calculated amount."""
        return f"{obj.amount:.2f} €"
    amount.short_description = 'Betrag'

