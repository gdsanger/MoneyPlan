from django.contrib import admin
from .models import Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'kind', 'color', 'archived']
    list_filter = ['kind', 'archived']
    search_fields = ['name', 'description']
