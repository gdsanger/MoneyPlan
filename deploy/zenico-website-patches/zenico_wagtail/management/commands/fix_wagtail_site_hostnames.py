from django.core.management.base import BaseCommand
from wagtail.models import Site

from zenico_wagtail.utils import normalize_site_hostname


class Command(BaseCommand):
    help = (
        'Fix Wagtail Site hostnames that incorrectly include a URL scheme '
        '(e.g. https://zenico.app instead of zenico.app).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show changes without saving them.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        updated = 0

        for site in Site.objects.all():
            cleaned = normalize_site_hostname(site.hostname)
            if cleaned == site.hostname:
                continue

            self.stdout.write(
                f'Site {site.id} ({site.site_name or site.hostname}): '
                f'{site.hostname!r} -> {cleaned!r}'
            )

            if not dry_run:
                site.hostname = cleaned
                site.save(update_fields=['hostname'])
                updated += 1

        if not dry_run and updated:
            Site.clear_site_root_paths_cache()

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run: no changes saved.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Updated {updated} site(s).'))
