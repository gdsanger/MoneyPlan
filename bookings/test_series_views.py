"""Tests for recurring series views"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from datetime import date, timedelta
from decimal import Decimal
from .models import Category, RecurringSeries, Booking


class SeriesViewsTestCase(TestCase):
    """Test cases for series views"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')

        # Create a category
        self.category = Category.objects.create(
            name='Test Category',
            icon='tag',
            color='#FF0000'
        )

    def test_series_list_empty(self):
        """Test series list view with no series"""
        response = self.client.get(reverse('bookings:series_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Noch keine wiederkehrenden Serien')

    def test_series_list_with_series(self):
        """Test series list view with existing series"""
        series = RecurringSeries.objects.create(
            description='Monthly Rent',
            amount=Decimal('-1000.00'),
            interval='monthly',
            start_date=date(2024, 1, 1),
            category=self.category
        )

        response = self.client.get(reverse('bookings:series_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Monthly Rent')
        self.assertContains(response, '1000')  # Template formats it with spaces

    def test_series_wizard_step1_get(self):
        """Test GET request to series wizard step 1"""
        response = self.client.get(reverse('bookings:series_wizard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Schritt 1: Konfiguration')
        self.assertContains(response, 'Beschreibung')
        self.assertContains(response, 'Betrag')

    def test_series_wizard_step1_post_valid(self):
        """Test POST request to series wizard step 1 with valid data"""
        data = {
            'description': 'Test Series',
            'amount': '100.00',
            'interval': 'monthly',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'category': self.category.id,
            'notes': 'Test notes'
        }

        response = self.client.post(reverse('bookings:series_wizard'), data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('bookings:series_preview'))

        # Check session data
        session = self.client.session
        self.assertIn('series_form_data', session)
        self.assertEqual(session['series_form_data']['description'], 'Test Series')

    def test_series_wizard_step1_post_invalid(self):
        """Test POST request to series wizard step 1 with invalid data"""
        data = {
            'description': '',  # Missing required field
            'amount': '100.00',
            'interval': 'monthly',
            'start_date': '2024-01-01',
        }

        response = self.client.post(reverse('bookings:series_wizard'), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Schritt 1: Konfiguration')

    def test_series_preview_without_session(self):
        """Test series preview without session data"""
        response = self.client.get(reverse('bookings:series_preview'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('bookings:series_wizard'))

    def test_series_preview_with_session(self):
        """Test series preview with valid session data"""
        # Set up session data
        session = self.client.session
        session['series_form_data'] = {
            'description': 'Test Series',
            'amount': '100.00',
            'interval': 'monthly',
            'start_date': '2024-01-01',
            'end_date': '2024-06-30',
            'category_id': self.category.id,
            'notes': 'Test notes'
        }
        session.save()

        response = self.client.get(reverse('bookings:series_preview'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Schritt 2: Vorschau')
        self.assertContains(response, 'Test Series')
        self.assertContains(response, 'Es werden')
        self.assertContains(response, 'Buchungen angelegt')

    def test_series_preview_back_button(self):
        """Test back button from series preview"""
        # Set up session data
        session = self.client.session
        session['series_form_data'] = {
            'description': 'Test Series',
            'amount': '100.00',
            'interval': 'monthly',
            'start_date': '2024-01-01',
            'end_date': '2024-06-30',
            'category_id': self.category.id,
            'notes': 'Test notes'
        }
        session.save()

        response = self.client.post(reverse('bookings:series_preview'), {'back': 'true'})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('bookings:series_wizard'))

    def test_series_confirm(self):
        """Test series confirmation and creation"""
        # Set up session data
        session = self.client.session
        session['series_form_data'] = {
            'description': 'Test Series',
            'amount': '100.00',
            'interval': 'monthly',
            'start_date': '2024-01-01',
            'end_date': '2024-03-01',
            'category_id': self.category.id,
            'notes': 'Test notes'
        }
        session.save()

        response = self.client.post(reverse('bookings:series_confirm'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('bookings:series_list'))

        # Check that series was created
        self.assertEqual(RecurringSeries.objects.count(), 1)
        series = RecurringSeries.objects.first()
        self.assertEqual(series.description, 'Test Series')
        self.assertEqual(series.amount, Decimal('100.00'))

        # Check that bookings were created
        self.assertTrue(Booking.objects.filter(series=series).count() > 0)

        # Check session was cleared
        self.assertNotIn('series_form_data', self.client.session)

    def test_series_delete(self):
        """Test series deletion"""
        # Create a series with bookings
        series = RecurringSeries.objects.create(
            description='Test Series',
            amount=Decimal('100.00'),
            interval='monthly',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 1),
            category=self.category
        )

        # Create some bookings
        Booking.objects.create(
            date=date(2024, 1, 1),
            description='Test Booking 1',
            amount=Decimal('100.00'),
            category=self.category,
            series=series
        )
        Booking.objects.create(
            date=date(2024, 2, 1),
            description='Test Booking 2',
            amount=Decimal('100.00'),
            category=self.category,
            series=series
        )

        self.assertEqual(Booking.objects.filter(series=series).count(), 2)

        # Delete the series
        response = self.client.post(reverse('bookings:series_delete', args=[series.id]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('bookings:series_list'))

        # Check that series and bookings were deleted
        self.assertEqual(RecurringSeries.objects.count(), 0)
        self.assertEqual(Booking.objects.count(), 0)

    def test_series_delete_requires_post(self):
        """Test that series delete requires POST method"""
        series = RecurringSeries.objects.create(
            description='Test Series',
            amount=Decimal('100.00'),
            interval='monthly',
            start_date=date(2024, 1, 1),
            category=self.category
        )

        response = self.client.get(reverse('bookings:series_delete', args=[series.id]))
        self.assertEqual(response.status_code, 405)

        # Series should still exist
        self.assertEqual(RecurringSeries.objects.count(), 1)

    def test_booking_list_series_filter(self):
        """Test filtering bookings by series"""
        series1 = RecurringSeries.objects.create(
            description='Series 1',
            amount=Decimal('100.00'),
            interval='monthly',
            start_date=date(2024, 1, 1),
            category=self.category
        )
        series2 = RecurringSeries.objects.create(
            description='Series 2',
            amount=Decimal('200.00'),
            interval='monthly',
            start_date=date(2024, 1, 1),
            category=self.category
        )

        # Create bookings for both series
        Booking.objects.create(
            date=date(2024, 1, 1),
            description='Booking 1',
            amount=Decimal('100.00'),
            category=self.category,
            series=series1
        )
        Booking.objects.create(
            date=date(2024, 1, 1),
            description='Booking 2',
            amount=Decimal('200.00'),
            category=self.category,
            series=series2
        )

        # Filter by series1
        response = self.client.get(reverse('bookings:list') + f'?series={series1.id}')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Booking 1')
        self.assertNotContains(response, 'Booking 2')

    def test_login_required(self):
        """Test that all views require login"""
        self.client.logout()

        urls = [
            reverse('bookings:series_list'),
            reverse('bookings:series_wizard'),
            reverse('bookings:series_preview'),
        ]

        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith('/accounts/login/'))
