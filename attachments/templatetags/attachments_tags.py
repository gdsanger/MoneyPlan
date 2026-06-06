from django import template
from attachments.services import get_attachments_for

register = template.Library()


@register.filter
def attachments_for(obj):
    """Return attachments queryset for a content object."""
    return get_attachments_for(obj)
