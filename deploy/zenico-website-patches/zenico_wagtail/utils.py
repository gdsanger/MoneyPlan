import re

_SCHEME_PREFIX = re.compile(r'^https?://', re.IGNORECASE)


def normalize_site_hostname(hostname: str) -> str:
    """Strip URL scheme and trailing slashes from a Wagtail Site hostname."""
    hostname = (hostname or '').strip().lower()
    hostname = _SCHEME_PREFIX.sub('', hostname)
    return hostname.rstrip('/')


def normalize_sitemap_location(url: str) -> str:
    """Fix duplicated schemes such as https://https://example.com/."""
    if not url:
        return url

    normalized = url
    while '://' in normalized.split('://', 1)[-1]:
        scheme, remainder = normalized.split('://', 1)
        normalized = f'{scheme}://{remainder.split("://", 1)[-1]}'

    return normalized
