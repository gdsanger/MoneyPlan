from wagtail.contrib.sitemaps import Sitemap as WagtailSitemap

from .utils import normalize_sitemap_location


class Sitemap(WagtailSitemap):
    """Wagtail sitemap that tolerates misconfigured Site hostnames."""

    def location(self, obj):
        return normalize_sitemap_location(obj.get_full_url(self.request))
