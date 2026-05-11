import os
import uuid
from pathlib import Path

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


def attachment_upload_path(instance, filename):
    """
    Stores files at:
    /data/uploads/<app_label>/<model>/<object_id>/<uuid>_<filename>

    Example:
    /data/uploads/bookings/booking/42/a1b2c3d4_rechnung_januar.pdf
    /data/uploads/tasks/task/7/e5f6g7h8_vertrag.pdf
    """
    ext = Path(filename).suffix
    safe_name = f"{uuid.uuid4().hex[:8]}_{Path(filename).stem[:50]}{ext}"
    ct = instance.content_type
    return str(Path('uploads') / ct.app_label / ct.model / str(instance.object_id) / safe_name)


class Attachment(models.Model):
    """
    Generic file attachment that can be linked to any model via ContentType.
    Files are stored on the filesystem under MEDIA_ROOT/uploads/.
    """
    # Generic relation — works with Booking, Task, or any future model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    file = models.FileField(upload_to=attachment_upload_path)
    filename = models.CharField(max_length=255)  # original filename
    file_size = models.PositiveIntegerField()  # bytes
    mime_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Anhang'
        verbose_name_plural = 'Anhänge'
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return self.filename

    @property
    def file_size_display(self):
        """Human-readable file size: '1,2 MB', '340 KB'"""
        size = self.file_size

        if size < 1024:
            return f"{size} Bytes"
        elif size < 1024 * 1024:
            kb = size / 1024
            return f"{kb:.0f} KB"
        else:
            mb = size / (1024 * 1024)
            return f"{mb:.1f} MB".replace('.', ',')

    def delete(self, *args, **kwargs):
        """Delete physical file on model deletion"""
        if self.file and os.path.isfile(self.file.path):
            os.remove(self.file.path)
        super().delete(*args, **kwargs)
