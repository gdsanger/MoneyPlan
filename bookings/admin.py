from django.contrib import admin
from .models import Category, RecurringSeries, Booking


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'color']
    search_fields = ['name']


@admin.register(RecurringSeries)
class RecurringSeriesAdmin(admin.ModelAdmin):
    list_display = ['description', 'amount', 'interval', 'start_date', 'end_date', 'category']
    list_filter = ['interval', 'category']
    search_fields = ['description']
    date_hierarchy = 'start_date'


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['date', 'description', 'amount', 'status', 'category', 'series']
    list_filter = ['status', 'category', 'date']
    search_fields = ['description', 'notes']
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at']
