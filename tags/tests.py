from decimal import Decimal
from datetime import date

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase, Client as TestClient
from django.urls import reverse

from bookings.models import Booking, Category
from timetracking.models import Client, TimeEntry
from .models import Tag
from .forms import TagForm


class TagModelTestCase(TestCase):
    """Tests for the Tag model itself."""

    def test_create_tag(self):
        tag = Tag.objects.create(name='Website-Relaunch', kind='projekt', color='#ff0000')
        self.assertEqual(tag.name, 'Website-Relaunch')
        self.assertEqual(tag.kind, 'projekt')
        self.assertFalse(tag.archived)

    def test_unique_together_kind_and_name(self):
        Tag.objects.create(name='Acme', kind='kunde')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Tag.objects.create(name='Acme', kind='kunde')

    def test_same_name_allowed_for_different_kind(self):
        Tag.objects.create(name='Acme', kind='kunde')
        # Same name but different dimension must be allowed
        tag = Tag.objects.create(name='Acme', kind='projekt')
        self.assertEqual(tag.name, 'Acme')

    def test_attach_tag_to_booking(self):
        category = Category.objects.create(name='Sonstiges', category_type='neutral')
        booking = Booking.objects.create(
            date=date(2026, 1, 15),
            description='Testbuchung',
            amount=Decimal('10.00'),
            category=category,
        )
        tag = Tag.objects.create(name='Projekt A', kind='projekt')

        booking.tags.add(tag)

        self.assertIn(tag, booking.tags.all())
        self.assertIn(booking, tag.bookings.all())

    def test_attach_tag_to_time_entry(self):
        client = Client.objects.create(name='Kunde AB')
        entry = TimeEntry.objects.create(
            client=client,
            date=date(2026, 1, 15),
            duration=Decimal('1.5'),
            hourly_rate=Decimal('100.00'),
            description='Beratung',
        )
        tag = Tag.objects.create(name='Kunde AB', kind='kunde')

        entry.tags.add(tag)

        self.assertIn(tag, entry.tags.all())
        self.assertIn(entry, tag.time_entries.all())


class TagFormTestCase(TestCase):
    """Tests for TagForm uniqueness validation."""

    def test_form_rejects_duplicate_kind_and_name_case_insensitive(self):
        Tag.objects.create(name='Acme', kind='kunde')
        form = TagForm(data={'name': 'acme', 'kind': 'kunde', 'description': '', 'color': '#6c757d'})
        self.assertFalse(form.is_valid())

    def test_form_allows_editing_same_instance(self):
        tag = Tag.objects.create(name='Acme', kind='kunde')
        form = TagForm(
            data={'name': 'Acme', 'kind': 'kunde', 'description': 'aktualisiert', 'color': '#6c757d'},
            instance=tag,
        )
        self.assertTrue(form.is_valid())


class TagViewsTestCase(TestCase):
    """Tests for the tag management CRUD views."""

    def setUp(self):
        self.client = TestClient()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.tag = Tag.objects.create(name='Projekt A', kind='projekt', color='#007bff')

    def test_tag_list_requires_login(self):
        response = self.client.get(reverse('tags:list'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

    def test_tag_list_view(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('tags:list'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tags/tag_list.html')
        self.assertEqual(response.context['total_tags'], 1)

    def test_tag_create(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('tags:create'), {
            'name': 'Kostenstelle 100',
            'kind': 'kostenstelle',
            'description': '',
            'color': '#6c757d',
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Tag.objects.filter(name='Kostenstelle 100', kind='kostenstelle').exists())

    def test_tag_edit(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('tags:edit', args=[self.tag.id]), {
            'name': 'Projekt A umbenannt',
            'kind': 'projekt',
            'description': '',
            'color': '#007bff',
        })

        self.assertEqual(response.status_code, 302)
        self.tag.refresh_from_db()
        self.assertEqual(self.tag.name, 'Projekt A umbenannt')

    def test_tag_toggle_archived(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('tags:toggle_archived', args=[self.tag.id]))

        self.assertEqual(response.status_code, 302)
        self.tag.refresh_from_db()
        self.assertTrue(self.tag.archived)

    def test_tag_delete_unused(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('tags:delete', args=[self.tag.id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Tag.objects.filter(id=self.tag.id).exists())

    def test_tag_delete_blocked_when_used(self):
        category = Category.objects.create(name='Sonstiges', category_type='neutral')
        booking = Booking.objects.create(
            date=date(2026, 1, 15),
            description='Testbuchung',
            amount=Decimal('10.00'),
            category=category,
        )
        booking.tags.add(self.tag)

        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('tags:delete', args=[self.tag.id]))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Tag.objects.filter(id=self.tag.id).exists())


class TagGroupedChoicesTestCase(TestCase):
    """Tests for Tag.grouped_choices(), used to build dimension-grouped Multi-Select widgets."""

    def test_groups_tags_by_kind_ordered(self):
        Tag.objects.create(name='Zebra Projekt', kind='projekt')
        Tag.objects.create(name='Alpha Projekt', kind='projekt')
        Tag.objects.create(name='Kunde XY', kind='kunde')

        groups = Tag.grouped_choices()
        group_labels = [label for label, _options in groups]
        self.assertEqual(group_labels, ['Kunde', 'Projekt'])

        projekt_options = dict(groups[group_labels.index('Projekt')][1])
        names = list(projekt_options.values())
        self.assertEqual(names, ['Alpha Projekt', 'Zebra Projekt'])

    def test_excludes_archived_by_default(self):
        Tag.objects.create(name='Aktiv', kind='sonstiges')
        Tag.objects.create(name='Archiviert', kind='sonstiges', archived=True)

        groups = Tag.grouped_choices()
        all_names = [name for _label, options in groups for _pk, name in options]
        self.assertIn('Aktiv', all_names)
        self.assertNotIn('Archiviert', all_names)

    def test_custom_queryset_overrides_default_filter(self):
        archived = Tag.objects.create(name='Archiviert', kind='sonstiges', archived=True)

        groups = Tag.grouped_choices(Tag.objects.filter(pk=archived.pk))
        all_names = [name for _label, options in groups for _pk, name in options]
        self.assertEqual(all_names, ['Archiviert'])

    def test_empty_queryset_returns_empty_list(self):
        self.assertEqual(Tag.grouped_choices(Tag.objects.none()), [])
