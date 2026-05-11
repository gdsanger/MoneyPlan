from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from django.apps import apps

from .services import handle_upload, get_attachments_for, delete_attachment
from .forms import AttachmentUploadForm


@login_required
def upload_attachment(request, app_label, model_name, object_id):
    """
    Upload a file and attach it to a specific object.

    URL: /attachments/upload/<app_label>/<model_name>/<object_id>/
    """
    # Get the model class
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError:
        return JsonResponse({'error': 'Model not found'}, status=404)

    # Get the object
    content_object = get_object_or_404(model, pk=object_id)

    if request.method == 'POST':
        form = AttachmentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                attachment = handle_upload(request.FILES['file'], content_object)

                if request.htmx:
                    # Return the new attachment row for HTMX
                    attachments = get_attachments_for(content_object)
                    content_type = ContentType.objects.get_for_model(content_object)
                    return render(request, 'attachments/_attachment_panel.html', {
                        'object': content_object,
                        'attachments': attachments,
                        'app_label': content_type.app_label,
                        'model_name': content_type.model,
                    })
                else:
                    return JsonResponse({
                        'success': True,
                        'attachment_id': attachment.id,
                        'filename': attachment.filename,
                        'file_size': attachment.file_size_display,
                    })
            except ValidationError as e:
                if request.htmx:
                    return render(request, 'attachments/_upload_form.html', {
                        'form': form,
                        'error': str(e.message),
                        'object': content_object,
                    })
                else:
                    return JsonResponse({'error': str(e.message)}, status=400)

    # GET request or form invalid
    attachments = get_attachments_for(content_object)

    if request.htmx:
        return render(request, 'attachments/_attachment_panel.html', {
            'object': content_object,
            'attachments': attachments,
            'app_label': app_label,
            'model_name': model_name,
        })

    return render(request, 'attachments/attachment_list.html', {
        'object': content_object,
        'attachments': attachments,
        'form': AttachmentUploadForm(),
        'app_label': app_label,
        'model_name': model_name,
    })


@login_required
def list_attachments(request, app_label, model_name, object_id):
    """
    List all attachments for a specific object.

    URL: /attachments/list/<app_label>/<model_name>/<object_id>/
    """
    # Get the model class
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError:
        return JsonResponse({'error': 'Model not found'}, status=404)

    # Get the object
    content_object = get_object_or_404(model, pk=object_id)
    attachments = get_attachments_for(content_object)
    content_type = ContentType.objects.get_for_model(content_object)

    if request.htmx:
        return render(request, 'attachments/_attachment_panel.html', {
            'object': content_object,
            'attachments': attachments,
            'app_label': content_type.app_label,
            'model_name': content_type.model,
        })

    return render(request, 'attachments/attachment_list.html', {
        'object': content_object,
        'attachments': attachments,
        'form': AttachmentUploadForm(),
        'app_label': app_label,
        'model_name': model_name,
    })


@login_required
def delete_attachment_view(request, attachment_id):
    """
    Delete a specific attachment.

    URL: /attachments/delete/<attachment_id>/
    Method: POST only
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    success = delete_attachment(attachment_id)

    if success:
        if request.htmx:
            # Return empty response - HTMX will remove the row
            return HttpResponse('')
        else:
            return JsonResponse({'success': True})
    else:
        if request.htmx:
            return HttpResponse('Anhang nicht gefunden', status=404)
        else:
            return JsonResponse({'error': 'Attachment not found'}, status=404)
