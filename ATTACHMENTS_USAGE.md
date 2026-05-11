# File Upload & Attachment Service

This document describes how to use the attachment service to add file upload functionality to any model in the MoneyPlan application.

## Overview

The attachments app provides a generic file attachment service that can link files to any Django model (Booking, Task, etc.) using ContentType generic relations.

## Features

- **Generic Relations**: Works with any Django model
- **File Validation**:
  - Size limit: 10 MB
  - MIME type validation (PDF, images, Office docs, CSV, text)
- **Structured Storage**: Files stored at `/data/uploads/<app>/<model>/<id>/<uuid>_filename`
- **HTMX Support**: Full HTMX support for seamless uploads
- **Automatic Cleanup**: Physical files deleted when attachment records are removed

## Usage

### 1. Add Attachment Panel to a Template

To add file upload functionality to any detail/edit page, include the attachment panel:

```django
{% load crispy_forms_tags %}

<h2>Booking Details</h2>
<!-- Your booking details here -->

{% include 'attachments/_attachment_panel.html' with object=booking app_label='bookings' model_name='booking' %}
```

**Required context variables:**
- `object` - The model instance to attach files to
- `app_label` - The app name (e.g., 'bookings')
- `model_name` - The model name (e.g., 'booking')

### 2. Using Attachment Services in Python

```python
from attachments.services import handle_upload, get_attachments_for, delete_attachment
from bookings.models import Booking

# Get a booking
booking = Booking.objects.get(pk=1)

# Upload a file
from django.core.files.uploadedfile import InMemoryUploadedFile
attachment = handle_upload(uploaded_file, booking)

# Get all attachments for a booking
attachments = get_attachments_for(booking)

# Delete an attachment
success = delete_attachment(attachment_id)
```

### 3. URL Patterns

The attachments app provides these URL endpoints:

```
POST   /attachments/upload/<app_label>/<model_name>/<object_id>/
GET    /attachments/list/<app_label>/<model_name>/<object_id>/
POST   /attachments/delete/<attachment_id>/
```

### 4. Example View Integration

```python
from django.shortcuts import render, get_object_or_404
from attachments.services import get_attachments_for
from bookings.models import Booking

def booking_detail(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    attachments = get_attachments_for(booking)

    return render(request, 'bookings/detail.html', {
        'booking': booking,
        'attachments': attachments,
        'app_label': 'bookings',
        'model_name': 'booking',
    })
```

## Configuration

Settings are defined in `config/settings.py`:

```python
# Media files (user uploads)
MEDIA_ROOT = BASE_DIR / 'data'
MEDIA_URL = '/media/'

# File upload limits
MAX_UPLOAD_SIZE_MB = 10
ALLOWED_UPLOAD_MIME_TYPES = [
    'application/pdf',
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/csv',
    'text/plain',
]
```

## Model Structure

The `Attachment` model uses Django's ContentType framework for generic relations:

```python
class Attachment(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    file = models.FileField(upload_to=attachment_upload_path)
    filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    mime_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)
```

## Error Handling

The `handle_upload()` service function raises `ValidationError` for:
- Files exceeding 10 MB
- Disallowed MIME types

Example error handling:

```python
from django.core.exceptions import ValidationError

try:
    attachment = handle_upload(file, booking)
except ValidationError as e:
    # Display error message to user
    messages.error(request, str(e.message))
```

## Testing

The attachments app includes 19 comprehensive tests covering:
- Model functionality (upload path, file size display)
- Service functions (upload, retrieve, delete)
- View endpoints (authentication, HTMX support)
- File validation (size limits, MIME types)

Run tests with:
```bash
python manage.py test attachments
```

## Admin Interface

Attachments can be viewed and managed in the Django admin at `/admin/attachments/attachment/`.

Features:
- List display with file info, size, MIME type, upload date
- Filter by content type, MIME type, date
- Search by filename
- Manual addition disabled (use upload views instead)
