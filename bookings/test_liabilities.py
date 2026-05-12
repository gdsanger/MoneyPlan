"""
Unit tests for liability functionality
"""
from decimal import Decimal
from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from bookings.models import Category, Booking, Liability
from bookings.services import get_total_liabilities, get_liabilities_overview


class LiabilityModelTestCase(TestCase):
    """Test suite for Liability model"""

    def setUp(self):
        """Set up test data"""
        self.category = Category.objects.create(
            name="Darlehen", icon="bi-bank", color="#dc3545"
        )

    def test_liability_creation(self):
        """Test creating a liability"""
        liability = Liability.objects.create(
            name="Autokredit VW",
            description="Kredit für VW Golf",
            initial_amount=Decimal('10000.00'),
            start_date=date(2026, 1, 1),
            due_date=date(2028, 12, 31),
            category=self.category
        )
        self.assertEqual(liability.name, "Autokredit VW")
        self.assertEqual(liability.initial_amount, Decimal('10000.00'))

    def test_total_repaid_no_bookings(self):
        """Test total_repaid with no linked bookings"""
        liability = Liability.objects.create(
            name="Autokredit VW",
            initial_amount=Decimal('10000.00'),
            start_date=date(2026, 1, 1),
            category=self.category
        )
        self.assertEqual(liability.total_repaid, Decimal('0'))

    def test_total_repaid_with_bookings(self):
        """Test total_repaid calculation with linked bookings"""
        liability = Liability.objects.create(
            name="Autokredit VW",
            initial_amount=Decimal('10000.00'),
            start_date=date(2026, 1, 1),
            category=self.category
        )

        # Create linked expense bookings
        Booking.objects.create(
            date=date(2026, 2, 1),
            description="Kreditrate Januar",
            amount=Decimal('-500.00'),
            status='booked',
            category=self.category,
            liability=liability
        )
        Booking.objects.create(
            date=date(2026, 3, 1),
            description="Kreditrate Februar",
            amount=Decimal('-500.00'),
            status='booked',
            category=self.category,
            liability=liability
        )

        self.assertEqual(liability.total_repaid, Decimal('1000.00'))

    def test_total_repaid_ignores_planned_bookings(self):
        """Test that planned linked bookings do not count as repayments"""
        liability = Liability.objects.create(
            name="Autokredit VW",
            initial_amount=Decimal('10000.00'),
            start_date=date(2026, 1, 1),
            category=self.category
        )

        Booking.objects.create(
            date=date(2026, 2, 1),
            description="Kreditrate geplant",
            amount=Decimal('-500.00'),
            status='planned',
            category=self.category,
            liability=liability
        )

        self.assertEqual(liability.total_repaid, Decimal('0'))
        self.assertEqual(liability.remaining, Decimal('10000.00'))
        self.assertEqual(liability.repaid_percent, 0)

    def test_remaining_calculation(self):
        """Test remaining calculation"""
        liability = Liability.objects.create(
            name="Autokredit VW",
            initial_amount=Decimal('10000.00'),
            start_date=date(2026, 1, 1),
            category=self.category
        )

        Booking.objects.create(
            date=date(2026, 2, 1),
            description="Kreditrate",
            amount=Decimal('-2500.00'),
            status='booked',
            category=self.category,
            liability=liability
        )

        self.assertEqual(liability.remaining, Decimal('7500.00'))

    def test_repaid_percent(self):
        """Test repaid_percent calculation"""
        liability = Liability.objects.create(
            name="Autokredit VW",
            initial_amount=Decimal('10000.00'),
            start_date=date(2026, 1, 1),
            category=self.category
        )

        Booking.objects.create(
            date=date(2026, 2, 1),
            description="Kreditrate",
            amount=Decimal('-5000.00'),
            status='booked',
            category=self.category,
            liability=liability
        )

        self.assertEqual(liability.repaid_percent, 50)

    def test_is_closed_false(self):
        """Test is_closed when liability is still open"""
        liability = Liability.objects.create(
            name="Autokredit VW",
            initial_amount=Decimal('10000.00'),
            start_date=date(2026, 1, 1),
            category=self.category
        )

        Booking.objects.create(
            date=date(2026, 2, 1),
            description="Kreditrate",
            amount=Decimal('-5000.00'),
            status='booked',
            category=self.category,
            liability=liability
        )

        self.assertFalse(liability.is_closed)

    def test_is_closed_true(self):
        """Test is_closed when liability is fully repaid"""
        liability = Liability.objects.create(
            name="Autokredit VW",
            initial_amount=Decimal('10000.00'),
            start_date=date(2026, 1, 1),
            category=self.category
        )

        Booking.objects.create(
            date=date(2026, 2, 1),
            description="Kreditrate",
            amount=Decimal('-10000.00'),
            status='booked',
            category=self.category,
            liability=liability
        )

        self.assertTrue(liability.is_closed)


class LiabilityServiceTestCase(TestCase):
    """Test suite for liability services"""

    def setUp(self):
        """Set up test data"""
        self.category = Category.objects.create(
            name="Darlehen", icon="bi-bank", color="#dc3545"
        )

    def test_get_total_liabilities_empty(self):
        """Test total liabilities with no liabilities"""
        total = get_total_liabilities()
        self.assertEqual(total, Decimal('0.00'))

    def test_get_total_liabilities_with_open(self):
        """Test total liabilities calculation"""
        liability1 = Liability.objects.create(
            name="Autokredit VW",
            initial_amount=Decimal('10000.00'),
            start_date=date(2026, 1, 1),
            category=self.category
        )
        liability2 = Liability.objects.create(
            name="Hauskredit",
            initial_amount=Decimal('200000.00'),
            start_date=date(2026, 1, 1),
            category=self.category
        )

        # Add partial repayment for liability1
        Booking.objects.create(
            date=date(2026, 2, 1),
            description="Kreditrate",
            amount=Decimal('-2000.00'),
            status='booked',
            category=self.category,
            liability=liability1
        )

        total = get_total_liabilities()
        self.assertEqual(total, Decimal('208000.00'))  # 8000 + 200000

    def test_get_liabilities_overview(self):
        """Test get_liabilities_overview function"""
        liability = Liability.objects.create(
            name="Autokredit VW",
            initial_amount=Decimal('10000.00'),
            start_date=date(2026, 1, 1),
            category=self.category
        )

        Booking.objects.create(
            date=date(2026, 2, 1),
            description="Kreditrate",
            amount=Decimal('-2000.00'),
            status='booked',
            category=self.category,
            liability=liability
        )

        overview = get_liabilities_overview()
        self.assertEqual(len(overview), 1)
        self.assertEqual(overview[0]['liability'], liability)
        self.assertEqual(overview[0]['total_repaid'], Decimal('2000.00'))
        self.assertEqual(overview[0]['remaining'], Decimal('8000.00'))
        self.assertEqual(overview[0]['repaid_percent'], 20)
        self.assertFalse(overview[0]['is_closed'])


class LiabilityViewTestCase(TestCase):
    """Test suite for liability views"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')

        self.category = Category.objects.create(
            name="Darlehen", icon="bi-bank", color="#dc3545"
        )

    def test_liability_list_view(self):
        """Test liability list view"""
        response = self.client.get(reverse('bookings:liability_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/liability_list.html')

    def test_liability_create_get(self):
        """Test liability create view GET"""
        response = self.client.get(reverse('bookings:liability_create'))
        self.assertEqual(response.status_code, 200)

    def test_liability_create_post(self):
        """Test liability create view POST"""
        data = {
            'name': 'Test Liability',
            'initial_amount': '5000.00',
            'start_date': '2026-01-01',
            'category': self.category.id,
        }
        response = self.client.post(reverse('bookings:liability_create'), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        self.assertEqual(Liability.objects.count(), 1)

    def test_liability_detail_view(self):
        """Test liability detail view"""
        liability = Liability.objects.create(
            name="Test Liability",
            initial_amount=Decimal('5000.00'),
            start_date=date(2026, 1, 1),
            category=self.category
        )
        response = self.client.get(reverse('bookings:liability_detail', args=[liability.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/liability_detail.html')

    def test_liability_delete(self):
        """Test liability delete"""
        liability = Liability.objects.create(
            name="Test Liability",
            initial_amount=Decimal('5000.00'),
            start_date=date(2026, 1, 1),
            category=self.category
        )
        response = self.client.post(reverse('bookings:liability_delete', args=[liability.id]))
        self.assertEqual(response.status_code, 302)  # Redirect after success
        self.assertEqual(Liability.objects.count(), 0)

    def test_booking_with_liability(self):
        """Test creating booking linked to liability"""
        liability = Liability.objects.create(
            name="Test Liability",
            initial_amount=Decimal('5000.00'),
            start_date=date(2026, 1, 1),
            category=self.category
        )

        booking = Booking.objects.create(
            date=date(2026, 2, 1),
            description="Repayment",
            amount=Decimal('-1000.00'),
            status='booked',
            category=self.category,
            liability=liability
        )

        self.assertEqual(booking.liability, liability)
        self.assertEqual(liability.total_repaid, Decimal('1000.00'))
