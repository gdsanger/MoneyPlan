from django.contrib import admin
from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'due_date', 'priority', 'status']
    list_filter = ['status', 'priority']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at']
