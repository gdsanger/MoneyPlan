"""Tests for Tag assignment, display, filtering and bulk actions on time entries."""
from decimal import Decimal
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, Client as HttpClient
from django.urls import reverse

from timetracking.models import TimeEntry, Client
from timetracking.forms import TimeEntryForm
from tags.models import Tag


class TimeEntryFormTagsTestCase(TestCase):
    """Tags im Zeiterfassungsformular zuweisen"""

    def setUp(self):
        self.client_obj = Client.objects.create(name='Kunde A')
        self.tag_projekt = Tag.objects.create(name='Website-Relaunch', kind='projekt')
        self.tag_kunde = Tag.objects.create(name='Kunde XY', kind='kunde')
        self.tag_archived = Tag.objects.create(name='Altes Projekt', kind='projekt', archived=True)

    def test_form_includes_tags_field(self):
        form = TimeEntryForm()
        self.assertIn('tags', form.fields)
        self.assertFalse(form.fields['tags'].required)

    def test_form_tags_queryset_excludes_archived_by_default(self):
        form = TimeEntryForm()
        queryset_ids = set(form.fields['tags'].queryset.values_list('pk', flat=True))
        self.assertIn(self.tag_projekt.pk, queryset_ids)
        self.assertNotIn(self.tag_archived.pk, queryset_ids)

    def test_form_tags_queryset_keeps_already_assigned_archived_tag(self):
        entry = TimeEntry.objects.create(
            client=self.client_obj, date=date(2026, 1, 1),
            duration=Decimal('1.5'), hourly_rate=Decimal('80.00'),
            description='Test',
        )
        entry.tags.add(self.tag_archived)
        form = TimeEntryForm(instance=entry)
        queryset_ids = set(form.fields['tags'].queryset.values_list('pk', flat=True))
        self.assertIn(self.tag_archived.pk, queryset_ids)

    def test_form_choices_grouped_by_dimension(self):
        form = TimeEntryForm()
        choices = dict(form.fields['tags'].widget.choices)
        self.assertIn('Projekt', choices)
        self.assertIn('Kunde', choices)

    def test_saving_form_assigns_tags(self):
        form = TimeEntryForm(data={
            'client': self.client_obj.pk,
            'date': '2026-01-15',
            'duration': '2.0',
            'hourly_rate': '90.00',
            'description': 'Konzeption',
            'tags': [self.tag_projekt.pk, self.tag_kunde.pk],
        })
        self.assertTrue(form.is_valid(), form.errors)
        entry = form.save()
        self.assertEqual(
            set(entry.tags.values_list('pk', flat=True)),
            {self.tag_projekt.pk, self.tag_kunde.pk},
        )


class TimeEntryListTagsDisplayAndFilterTestCase(TestCase):
    """Tags in der Zeiterfassungsliste anzeigen und filtern"""

    def setUp(self):
        self.client = HttpClient()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')

        self.client_obj = Client.objects.create(name='Kunde A')
        self.tag_projekt = Tag.objects.create(name='Website-Relaunch', kind='projekt', color='#ff0000')
        self.tag_kunde = Tag.objects.create(name='Kunde XY', kind='kunde')

        self.tagged_entry = TimeEntry.objects.create(
            client=self.client_obj, date=date(2026, 1, 15),
            duration=Decimal('1.5'), hourly_rate=Decimal('80.00'),
            description='Getaggter Eintrag',
        )
        self.tagged_entry.tags.add(self.tag_projekt)

        self.untagged_entry = TimeEntry.objects.create(
            client=self.client_obj, date=date(2026, 1, 16),
            duration=Decimal('1.0'), hourly_rate=Decimal('80.00'),
            description='Ohne Tag',
        )

    def test_list_displays_tag_name_and_color(self):
        response = self.client.get(reverse('timetracking:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Website-Relaunch')
        self.assertContains(response, self.tag_projekt.color)

    def test_filter_by_tag(self):
        response = self.client.get(reverse('timetracking:list'), {'tag': self.tag_projekt.pk})
        entries = list(response.context['entries'])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].pk, self.tagged_entry.pk)

    def test_filter_by_tag_kind(self):
        response = self.client.get(reverse('timetracking:list'), {'tag_kind': 'projekt'})
        entries = list(response.context['entries'])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].pk, self.tagged_entry.pk)

    def test_filter_by_tag_kind_no_match_returns_empty(self):
        response = self.client.get(reverse('timetracking:list'), {'tag_kind': 'kostenstelle'})
        entries = list(response.context['entries'])
        self.assertEqual(len(entries), 0)

    def test_no_tag_filter_returns_all(self):
        response = self.client.get(reverse('timetracking:list'))
        entries = list(response.context['entries'])
        self.assertEqual(len(entries), 2)


class TimeEntryBulkTagTestCase(TestCase):
    """Bulk-Zuordnung/-Entfernung von Tags für mehrere Zeiteinträge"""

    def setUp(self):
        self.client = HttpClient()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        self.client_obj = Client.objects.create(name='Kunde A')
        self.tag = Tag.objects.create(name='Website-Relaunch', kind='projekt')

        self.entry1 = TimeEntry.objects.create(
            client=self.client_obj, date=date(2026, 1, 15),
            duration=Decimal('1.5'), hourly_rate=Decimal('80.00'),
            description='Eintrag 1',
        )
        self.entry2 = TimeEntry.objects.create(
            client=self.client_obj, date=date(2026, 1, 16),
            duration=Decimal('1.0'), hourly_rate=Decimal('80.00'),
            description='Eintrag 2',
        )

    def test_bulk_tag_requires_login(self):
        response = self.client.post(reverse('timetracking:bulk_tag'), {
            'selected_entries': [self.entry1.pk],
            'tag': self.tag.pk,
            'bulk_action': 'add',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

    def test_bulk_tag_requires_post(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('timetracking:bulk_tag'))
        self.assertEqual(response.status_code, 405)

    def test_bulk_assign_tag_to_multiple_entries(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('timetracking:bulk_tag'), {
            'selected_entries': [self.entry1.pk, self.entry2.pk],
            'tag': self.tag.pk,
            'bulk_action': 'add',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.tag, self.entry1.tags.all())
        self.assertIn(self.tag, self.entry2.tags.all())

    def test_bulk_remove_tag_from_multiple_entries(self):
        self.entry1.tags.add(self.tag)
        self.entry2.tags.add(self.tag)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('timetracking:bulk_tag'), {
            'selected_entries': [self.entry1.pk, self.entry2.pk],
            'tag': self.tag.pk,
            'bulk_action': 'remove',
        })
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(self.tag, self.entry1.tags.all())
        self.assertNotIn(self.tag, self.entry2.tags.all())

    def test_bulk_tag_without_selection_does_not_error(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('timetracking:bulk_tag'), {
            'selected_entries': [],
            'tag': self.tag.pk,
            'bulk_action': 'add',
        })
        self.assertEqual(response.status_code, 302)

    def test_bulk_tag_without_tag_does_not_error(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('timetracking:bulk_tag'), {
            'selected_entries': [self.entry1.pk],
            'tag': '',
            'bulk_action': 'add',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.entry1.tags.count(), 0)
