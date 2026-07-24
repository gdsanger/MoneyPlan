from django import template

register = template.Library()


@register.filter
def contrast_text_color(hex_color):
    """Gibt '#000000' oder '#ffffff' zurück, je nachdem was auf hex_color besser lesbar ist (YIQ-Helligkeit)."""
    value = (hex_color or "").lstrip("#")
    if len(value) != 6:
        return "#ffffff"
    try:
        r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return "#ffffff"
    yiq = (r * 299 + g * 587 + b * 114) / 1000
    return "#000000" if yiq >= 128 else "#ffffff"
