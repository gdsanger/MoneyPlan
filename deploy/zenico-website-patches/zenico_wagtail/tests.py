from django.test import SimpleTestCase

from zenico_wagtail.utils import normalize_site_hostname, normalize_sitemap_location


class NormalizeSiteHostnameTests(SimpleTestCase):
    def test_strips_https_scheme(self):
        self.assertEqual(normalize_site_hostname('https://zenico.app'), 'zenico.app')

    def test_strips_http_scheme(self):
        self.assertEqual(normalize_site_hostname('http://zenico.app/'), 'zenico.app')

    def test_leaves_plain_hostname_unchanged(self):
        self.assertEqual(normalize_site_hostname('zenico.app'), 'zenico.app')


class NormalizeSitemapLocationTests(SimpleTestCase):
    def test_fixes_double_https(self):
        self.assertEqual(
            normalize_sitemap_location('https://https://zenico.app/faq/'),
            'https://zenico.app/faq/',
        )

    def test_leaves_valid_url_unchanged(self):
        self.assertEqual(
            normalize_sitemap_location('https://zenico.app/faq/'),
            'https://zenico.app/faq/',
        )
