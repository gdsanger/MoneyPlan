"""Custom template tags for the dashboard app."""
import bleach
import markdown
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

MARKDOWN_EXTENSIONS = ['extra', 'nl2br', 'sane_lists']

ALLOWED_TAGS = [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'ul', 'ol', 'li',
    'strong', 'em', 'code', 'pre', 'blockquote',
    'hr', 'br',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
]

ALLOWED_ATTRIBUTES = {
    'th': ['align'],
    'td': ['align'],
}


@register.filter(name='render_markdown')
def render_markdown(text):
    """Render Markdown text as sanitized HTML."""
    if not text:
        return ''

    html = markdown.markdown(
        text,
        extensions=MARKDOWN_EXTENSIONS,
    )
    sanitized = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )
    return mark_safe(sanitized)
