from django.contrib import admin
from .models import Attachment


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ['filename', 'content_type', 'object_id', 'file_size_display', 'mime_type', 'uploaded_at']
    list_filter = ['content_type', 'mime_type', 'uploaded_at']
    search_fields = ['filename']
    readonly_fields = ['uploaded_at', 'file_size_display']
    date_hierarchy = 'uploaded_at'

    def has_add_permission(self, request):
        # Prevent manual addition through admin - use upload views instead
        return False
