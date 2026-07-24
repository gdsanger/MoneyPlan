from decimal import Decimal
from datetime import date

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from bookings.models import Booking, Category, ReconciliationLog


class ReconciliationViewTestCase(TestCase):
    """Test cases for the Kontenabgleich (account reconciliation) view"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        # Migration 0007 seeds a "Neutral" category already; reuse it like production code does.
        self.neutral_category = Category.objects.get(category_type='neutral')
        self.income_category = Category.objects.create(
            name='Gehalt',
            category_type='income',
        )

        Booking.objects.create(
            date=date(2026, 1, 1),
            description='Gehalt',
            amount=Decimal('2000.00'),
            status='booked',
            category=self.income_category,
        )
        Booking.objects.create(
            date=date(2026, 1, 5),
            description='Geplante Ausgabe',
            amount=Decimal('-100.00'),
            status='planned',
            category=self.income_category,
        )

    def test_reconciliation_view_requires_login(self):
        response = self.client.get(reverse('bookings:reconciliation'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

    def test_reconciliation_view_shows_moneyplan_soll(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('bookings:reconciliation'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/reconciliation.html')
        # Only the booked booking counts, the planned one doesn't
        self.assertEqual(response.context['expected_balance'], Decimal('2000.00'))
        self.assertIsNone(response.context['actual_balance'])

    def test_reconciliation_view_computes_difference_from_query_param(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('bookings:reconciliation'), {'actual_balance': '2050.00'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['actual_balance'], Decimal('2050.00'))
        self.assertEqual(response.context['difference'], Decimal('50.00'))

    def test_create_reconciliation_booking_with_positive_difference(self):
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(reverse('bookings:reconciliation_create'), {
            'actual_balance': '2050.00',
            'category': self.neutral_category.pk,
        })

        self.assertRedirects(response, reverse('bookings:reconciliation'))

        booking = Booking.objects.get(description='Kontenabgleich')
        self.assertEqual(booking.amount, Decimal('50.00'))
        self.assertEqual(booking.status, 'booked')
        self.assertEqual(booking.date, date.today())
        self.assertEqual(booking.category, self.neutral_category)

        log = ReconciliationLog.objects.get()
        self.assertEqual(log.actual_balance, Decimal('2050.00'))
        self.assertEqual(log.expected_balance, Decimal('2000.00'))
        self.assertEqual(log.difference, Decimal('50.00'))
        self.assertEqual(log.booking, booking)

    def test_reconciliation_booking_excluded_from_statistics(self):
        self.client.login(username='testuser', password='testpass123')

        self.client.post(reverse('bookings:reconciliation_create'), {
            'actual_balance': '1900.00',
            'category': self.neutral_category.pk,
        })

        booking = Booking.objects.get(description='Kontenabgleich')
        self.assertFalse(booking.category.is_statistical)

        # But the balance (Ist-Saldo) does reflect it
        from bookings.services import get_current_balance
        self.assertEqual(get_current_balance(), Decimal('1900.00'))

    def test_no_booking_created_when_balances_match(self):
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(reverse('bookings:reconciliation_create'), {
            'actual_balance': '2000.00',
            'category': self.neutral_category.pk,
        })

        self.assertRedirects(response, reverse('bookings:reconciliation'))
        self.assertFalse(Booking.objects.filter(description='Kontenabgleich').exists())

        log = ReconciliationLog.objects.get()
        self.assertEqual(log.difference, Decimal('0.00'))
        self.assertIsNone(log.booking)

    def test_reconciliation_create_requires_category(self):
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(reverse('bookings:reconciliation_create'), {
            'actual_balance': '2050.00',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Booking.objects.filter(description='Kontenabgleich').exists())
        self.assertFalse(ReconciliationLog.objects.exists())
