"""
Service functions for attachments.

Conventions:
- All functions return Attachment instances or QuerySets
- Validations raise Django's ValidationError
- File operations are handled safely with proper error handling
"""
import os
import magic

from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import InMemoryUploadedFile

from .models import Attachment


def handle_upload(file: InMemoryUploadedFile, content_object) -> Attachment:
    """
    Validates and saves an uploaded file as Attachment linked to content_object.

    Args:
        file: The uploaded file from request.FILES
        content_object: Any Django model instance (e.g., Booking, Task)

    Returns:
        The created Attachment instance

    Raises:
        ValidationError: If file is too large or MIME type is not allowed
    """
    # Validate file size
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024  # Convert MB to bytes
    if file.size > max_size:
        raise ValidationError(
            f'Datei ist zu groß. Maximale Größe: {settings.MAX_UPLOAD_SIZE_MB} MB'
        )

    # Detect MIME type from file content
    file.seek(0)
    mime = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)

    # Validate MIME type
    allowed_types = settings.ALLOWED_UPLOAD_MIME_TYPES
    if mime not in allowed_types:
        raise ValidationError(
            f'Dateityp "{mime}" ist nicht erlaubt. '
            f'Erlaubte Typen: PDF, Bilder, Office-Dokumente, CSV, Text'
        )

    # Sanitize filename - strip path components, limit length
    original_filename = os.path.basename(file.name)
    if len(original_filename) > 200:
        name_without_ext = os.path.splitext(original_filename)[0][:190]
        ext = os.path.splitext(original_filename)[1]
        original_filename = name_without_ext + ext

    # Get ContentType for the content_object
    content_type = ContentType.objects.get_for_model(content_object)

    # Create Attachment instance
    attachment = Attachment(
        content_type=content_type,
        object_id=content_object.pk,
        file=file,
        filename=original_filename,
        file_size=file.size,
        mime_type=mime,
    )
    attachment.save()

    return attachment


def get_attachments_for(content_object):
    """
    Returns all attachments for a given object.

    Args:
        content_object: Any Django model instance (e.g., Booking, Task)

    Returns:
        QuerySet of Attachment instances, ordered by -uploaded_at
    """
    content_type = ContentType.objects.get_for_model(content_object)
    return Attachment.objects.filter(
        content_type=content_type,
        object_id=content_object.pk
    )


def delete_attachment(attachment_id: int) -> bool:
    """
    Deletes attachment record and physical file.

    Args:
        attachment_id: Primary key of the Attachment

    Returns:
        True on success, False if attachment not found
    """
    try:
        attachment = Attachment.objects.get(pk=attachment_id)
        attachment.delete()  # Model's delete() handles file deletion
        return True
    except Attachment.DoesNotExist:
        return False
