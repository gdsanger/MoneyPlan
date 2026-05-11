"""
Tests for dashboard app views and chart endpoints.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from decimal import Decimal
from datetime import date, timedelta
from bookings.models import Category, Booking
from alerts.models import Alert


class DashboardViewTest(TestCase):
    """Test dashboard index view."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.category = Category.objects.create(
            name='Test Category',
            icon='cash',
            color='#28a745'
        )

    def test_dashboard_requires_login(self):
        """Test that dashboard requires authentication."""
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_dashboard_loads_with_no_data(self):
        """Test dashboard loads with no bookings."""
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')
        self.assertContains(response, '0,00 €')

    def test_dashboard_shows_kpi_data(self):
        """Test dashboard displays KPI data correctly."""
        self.client.login(username='testuser', password='testpass')

        # Create test bookings
        Booking.objects.create(
            date=date.today() - timedelta(days=1),
            description='Income',
            amount=Decimal('1000.00'),
            status='booked',
            category=self.category
        )
        Booking.objects.create(
            date=date.today() + timedelta(days=5),
            description='Expense',
            amount=Decimal('-200.00'),
            status='planned',
            category=self.category
        )

        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Geldmittel verfügbar')
        self.assertContains(response, 'Offene Ausgaben')
        self.assertContains(response, 'Offene Einnahmen')


class ChartDataTest(TestCase):
    """Test chart data endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.category = Category.objects.create(
            name='Test Category',
            icon='cash',
            color='#28a745'
        )

    def test_forecast_chart_data_requires_login(self):
        """Test forecast endpoint requires authentication."""
        response = self.client.get(reverse('dashboard:forecast_data'))
        self.assertEqual(response.status_code, 302)

    def test_forecast_chart_data_returns_json(self):
        """Test forecast endpoint returns valid JSON."""
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(reverse('dashboard:forecast_data'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        data = response.json()
        self.assertIn('labels', data)
        self.assertIn('datasets', data)

    def test_category_chart_data_returns_json(self):
        """Test category endpoint returns valid JSON."""
        self.client.login(username='testuser', password='testpass')

        # Create expense booking
        Booking.objects.create(
            date=date.today(),
            description='Test Expense',
            amount=Decimal('-100.00'),
            status='booked',
            category=self.category
        )

        response = self.client.get(reverse('dashboard:category_data'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('labels', data)
        self.assertIn('datasets', data)

    def test_donut_chart_data_returns_json(self):
        """Test donut endpoint returns valid JSON."""
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(reverse('dashboard:donut_data'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('labels', data)
        self.assertIn('datasets', data)
        self.assertEqual(data['labels'], ['Einnahmen', 'Ausgaben'])


class MarkAsBookedTest(TestCase):
    """Test mark as booked functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.category = Category.objects.create(
            name='Test Category',
            icon='cash',
            color='#28a745'
        )
        self.booking = Booking.objects.create(
            date=date.today() + timedelta(days=5),
            description='Test Booking',
            amount=Decimal('-100.00'),
            status='planned',
            category=self.category
        )

    def test_mark_as_booked_requires_login(self):
        """Test mark as booked requires authentication."""
        response = self.client.post(
            reverse('dashboard:mark_as_booked', args=[self.booking.id])
        )
        self.assertEqual(response.status_code, 302)

    def test_mark_as_booked_updates_status(self):
        """Test marking booking as booked."""
        self.client.login(username='testuser', password='testpass')
        response = self.client.post(
            reverse('dashboard:mark_as_booked', args=[self.booking.id])
        )
        self.assertEqual(response.status_code, 200)

        # Verify booking status updated
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, 'booked')

    def test_mark_as_booked_only_post(self):
        """Test mark as booked only accepts POST."""
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(
            reverse('dashboard:mark_as_booked', args=[self.booking.id])
        )
        self.assertEqual(response.status_code, 405)


class YearOverviewTest(TestCase):
    """Test year overview functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.category = Category.objects.create(
            name='Test Category',
            icon='cash',
            color='#28a745'
        )

    def test_year_overview_requires_login(self):
        """Test year overview requires authentication."""
        response = self.client.get(reverse('dashboard:year_overview'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_year_overview_loads_with_no_data(self):
        """Test year overview loads with no bookings."""
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(reverse('dashboard:year_overview'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Jahresübersicht')
        self.assertContains(response, 'Gesamteinnahmen')
        self.assertContains(response, 'Gesamtausgaben')
        self.assertContains(response, 'Jahresergebnis')

    def test_year_overview_with_specific_year(self):
        """Test year overview with specific year parameter."""
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(reverse('dashboard:year_overview_detail', args=[2025]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '2025')

    def test_year_overview_displays_bookings(self):
        """Test year overview displays booking data correctly."""
        self.client.login(username='testuser', password='testpass')

        # Create bookings in different months
        Booking.objects.create(
            date=date(2026, 1, 15),
            description='January Income',
            amount=Decimal('3000.00'),
            status='booked',
            category=self.category
        )
        Booking.objects.create(
            date=date(2026, 1, 20),
            description='January Expense',
            amount=Decimal('-1000.00'),
            status='booked',
            category=self.category
        )
        Booking.objects.create(
            date=date(2026, 2, 10),
            description='February Income',
            amount=Decimal('2500.00'),
            status='booked',
            category=self.category
        )

        response = self.client.get(reverse('dashboard:year_overview_detail', args=[2026]))
        self.assertEqual(response.status_code, 200)

        # Check for German month names
        self.assertContains(response, 'Januar')
        self.assertContains(response, 'Februar')

        # Check for totals (German formatting: comma as decimal separator)
        self.assertContains(response, '5500,00')  # Total income (3000 + 2500)
        self.assertContains(response, '1000,00')  # Total expenses

    def test_year_overview_htmx_returns_partial(self):
        """Test year overview returns partial template for HTMX requests."""
        self.client.login(username='testuser', password='testpass')

        # Simulate HTMX request
        response = self.client.get(
            reverse('dashboard:year_overview_detail', args=[2025]),
            HTTP_HX_REQUEST='true'
        )
        self.assertEqual(response.status_code, 200)

        # Should contain grid content but not full page structure
        self.assertContains(response, 'Gesamteinnahmen')
        self.assertNotContains(response, 'Jahresübersicht')  # Page title not in partial

    def test_year_overview_navigation(self):
        """Test year navigation links are present."""
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(reverse('dashboard:year_overview_detail', args=[2025]))
        self.assertEqual(response.status_code, 200)

        # Check for previous/next year navigation
        self.assertContains(response, '2024')  # Previous year
        self.assertContains(response, '2026')  # Next year
        self.assertContains(response, 'hx-get')  # HTMX navigation

    def test_year_overview_shows_all_12_months(self):
        """Test year overview shows all 12 months."""
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(reverse('dashboard:year_overview'))
        self.assertEqual(response.status_code, 200)

        # All German month names should appear
        months = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
                  'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']
        for month in months:
            self.assertContains(response, month)

    def test_year_overview_calculates_best_worst_month(self):
        """Test year overview calculates best and worst months."""
        self.client.login(username='testuser', password='testpass')

        # Create bookings with different results
        Booking.objects.create(
            date=date(2026, 1, 15),
            description='Good Month',
            amount=Decimal('5000.00'),
            status='booked',
            category=self.category
        )
        Booking.objects.create(
            date=date(2026, 2, 15),
            description='Bad Month',
            amount=Decimal('-3000.00'),
            status='booked',
            category=self.category
        )

        response = self.client.get(reverse('dashboard:year_overview_detail', args=[2026]))
        self.assertEqual(response.status_code, 200)

        # Check for best/worst month indicators
        self.assertContains(response, 'Bestes Monat')
        self.assertContains(response, 'Schlechtestes Monat')

