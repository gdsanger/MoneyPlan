"""Tests for Tag assignment, display, filtering and bulk actions on bookings."""
from decimal import Decimal
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, Client as HttpClient
from django.urls import reverse

from bookings.models import Booking, Category
from bookings.forms import BookingForm, BookingFilterForm
from tags.models import Tag


class BookingFormTagsTestCase(TestCase):
    """Tags im Buchungsformular zuweisen"""

    def setUp(self):
        self.category = Category.objects.create(
            name='Test Kategorie', icon='wallet', color='#007bff'
        )
        self.tag_projekt = Tag.objects.create(name='Website-Relaunch', kind='projekt')
        self.tag_kunde = Tag.objects.create(name='Kunde XY', kind='kunde')
        self.tag_archived = Tag.objects.create(name='Altes Projekt', kind='projekt', archived=True)

    def test_form_includes_tags_field(self):
        form = BookingForm()
        self.assertIn('tags', form.fields)
        self.assertFalse(form.fields['tags'].required)

    def test_form_tags_queryset_excludes_archived_by_default(self):
        form = BookingForm()
        queryset_ids = set(form.fields['tags'].queryset.values_list('pk', flat=True))
        self.assertIn(self.tag_projekt.pk, queryset_ids)
        self.assertIn(self.tag_kunde.pk, queryset_ids)
        self.assertNotIn(self.tag_archived.pk, queryset_ids)

    def test_form_tags_queryset_keeps_already_assigned_archived_tag(self):
        booking = Booking.objects.create(
            date=date(2026, 1, 1), description='Test', amount=Decimal('10.00'),
            category=self.category,
        )
        booking.tags.add(self.tag_archived)
        form = BookingForm(instance=booking)
        queryset_ids = set(form.fields['tags'].queryset.values_list('pk', flat=True))
        self.assertIn(self.tag_archived.pk, queryset_ids)

    def test_form_choices_grouped_by_dimension(self):
        form = BookingForm()
        choices = dict(form.fields['tags'].widget.choices)
        self.assertIn('Projekt', choices)
        self.assertIn('Kunde', choices)

    def test_saving_form_assigns_tags(self):
        form = BookingForm(data={
            'date': '2026-01-15',
            'description': 'Einkauf',
            'amount': '-50.00',
            'category': self.category.pk,
            'status': 'booked',
            'tags': [self.tag_projekt.pk, self.tag_kunde.pk],
        })
        self.assertTrue(form.is_valid(), form.errors)
        booking = form.save()
        self.assertEqual(
            set(booking.tags.values_list('pk', flat=True)),
            {self.tag_projekt.pk, self.tag_kunde.pk},
        )


class BookingListTagsDisplayAndFilterTestCase(TestCase):
    """Tags in der Buchungsliste anzeigen und filtern"""

    def setUp(self):
        self.client = HttpClient()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')

        self.category = Category.objects.create(
            name='Test Kategorie', icon='wallet', color='#007bff'
        )
        self.tag_projekt = Tag.objects.create(name='Website-Relaunch', kind='projekt', color='#ff0000')
        self.tag_kunde = Tag.objects.create(name='Kunde XY', kind='kunde')

        self.tagged_booking = Booking.objects.create(
            date=date(2026, 1, 15), description='Getaggte Buchung',
            amount=Decimal('-50.00'), category=self.category,
        )
        self.tagged_booking.tags.add(self.tag_projekt)

        self.untagged_booking = Booking.objects.create(
            date=date(2026, 1, 16), description='Ohne Tag',
            amount=Decimal('-20.00'), category=self.category,
        )

    def test_list_displays_tag_name_and_color(self):
        response = self.client.get(reverse('bookings:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Website-Relaunch')
        self.assertContains(response, self.tag_projekt.color)

    def test_filter_by_tag(self):
        response = self.client.get(reverse('bookings:list'), {'tag': self.tag_projekt.pk})
        bookings = list(response.context['page_obj'])
        self.assertEqual(len(bookings), 1)
        self.assertEqual(bookings[0].pk, self.tagged_booking.pk)

    def test_filter_by_tag_kind(self):
        response = self.client.get(reverse('bookings:list'), {'tag_kind': 'projekt'})
        bookings = list(response.context['page_obj'])
        self.assertEqual(len(bookings), 1)
        self.assertEqual(bookings[0].pk, self.tagged_booking.pk)

    def test_filter_by_tag_kind_no_match_returns_empty(self):
        response = self.client.get(reverse('bookings:list'), {'tag_kind': 'kostenstelle'})
        bookings = list(response.context['page_obj'])
        self.assertEqual(len(bookings), 0)

    def test_no_tag_filter_returns_all(self):
        response = self.client.get(reverse('bookings:list'))
        bookings = list(response.context['page_obj'])
        self.assertEqual(len(bookings), 2)

    def test_filter_form_tag_choices_grouped(self):
        form = BookingFilterForm()
        choices = dict(form.fields['tag'].widget.choices)
        self.assertIn('Projekt', choices)
        self.assertIn('Kunde', choices)


class BookingBulkTagTestCase(TestCase):
    """Bulk-Zuordnung/-Entfernung von Tags für mehrere Buchungen"""

    def setUp(self):
        self.client = HttpClient()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        self.category = Category.objects.create(
            name='Test Kategorie', icon='wallet', color='#007bff'
        )
        self.tag = Tag.objects.create(name='Website-Relaunch', kind='projekt')

        self.booking1 = Booking.objects.create(
            date=date(2026, 1, 15), description='Buchung 1',
            amount=Decimal('-50.00'), category=self.category,
        )
        self.booking2 = Booking.objects.create(
            date=date(2026, 1, 16), description='Buchung 2',
            amount=Decimal('-20.00'), category=self.category,
        )

    def test_bulk_tag_requires_login(self):
        response = self.client.post(reverse('bookings:bulk_tag'), {
            'selected_bookings': [self.booking1.pk],
            'tag': self.tag.pk,
            'bulk_action': 'add',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

    def test_bulk_tag_requires_post(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('bookings:bulk_tag'))
        self.assertEqual(response.status_code, 405)

    def test_bulk_assign_tag_to_multiple_bookings(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('bookings:bulk_tag'), {
            'selected_bookings': [self.booking1.pk, self.booking2.pk],
            'tag': self.tag.pk,
            'bulk_action': 'add',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.tag, self.booking1.tags.all())
        self.assertIn(self.tag, self.booking2.tags.all())

    def test_bulk_remove_tag_from_multiple_bookings(self):
        self.booking1.tags.add(self.tag)
        self.booking2.tags.add(self.tag)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('bookings:bulk_tag'), {
            'selected_bookings': [self.booking1.pk, self.booking2.pk],
            'tag': self.tag.pk,
            'bulk_action': 'remove',
        })
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(self.tag, self.booking1.tags.all())
        self.assertNotIn(self.tag, self.booking2.tags.all())

    def test_bulk_tag_without_selection_does_not_error(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('bookings:bulk_tag'), {
            'selected_bookings': [],
            'tag': self.tag.pk,
            'bulk_action': 'add',
        })
        self.assertEqual(response.status_code, 302)

    def test_bulk_tag_without_tag_does_not_error(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('bookings:bulk_tag'), {
            'selected_bookings': [self.booking1.pk],
            'tag': '',
            'bulk_action': 'add',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.booking1.tags.count(), 0)
