"""
Unit tests for bookings views
"""
from decimal import Decimal
from datetime import date
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from bookings.models import Category, Booking


class MonthViewTestCase(TestCase):
    """Test suite for month_view"""

    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client = Client()
        self.client.login(username='testuser', password='testpass')

        # Create categories
        self.income_category = Category.objects.create(
            name="Gehalt", icon="wallet", color="#28a745"
        )
        self.expense_category = Category.objects.create(
            name="Miete", icon="house", color="#dc3545"
        )

    def test_month_view_requires_login(self):
        """Test that month view requires authentication"""
        self.client.logout()
        response = self.client.get(reverse('bookings:month_view'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_month_view_current_month(self):
        """Test month view defaults to current month"""
        response = self.client.get(reverse('bookings:month_view'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Monatsansicht')

        # Check context
        today = date.today()
        self.assertEqual(response.context['year'], today.year)
        self.assertEqual(response.context['month'], today.month)

    def test_month_view_specific_month(self):
        """Test month view with specific year and month"""
        response = self.client.get(
            reverse('bookings:month_view_detail', kwargs={'year': 2026, 'month': 5})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['year'], 2026)
        self.assertEqual(response.context['month'], 5)
        self.assertContains(response, 'Mai 2026')

    def test_month_view_invalid_month(self):
        """Test month view with invalid month defaults to current"""
        response = self.client.get(
            reverse('bookings:month_view_detail', kwargs={'year': 2026, 'month': 13})
        )
        self.assertEqual(response.status_code, 200)
        today = date.today()
        self.assertEqual(response.context['year'], today.year)
        self.assertEqual(response.context['month'], today.month)

    def test_month_view_carry_forward_calculation(self):
        """Test that carry forward balance is calculated correctly"""
        # Create bookings before May 2026
        Booking.objects.create(
            date=date(2026, 4, 1),
            description="April Income",
            amount=Decimal('1000.00'),
            status='booked',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 4, 15),
            description="April Expense",
            amount=Decimal('-500.00'),
            status='booked',
            category=self.expense_category
        )

        response = self.client.get(
            reverse('bookings:month_view_detail', kwargs={'year': 2026, 'month': 5})
        )

        # Carry forward should be 1000 - 500 = 500
        self.assertEqual(response.context['carry_forward'], Decimal('500.00'))

    def test_month_view_bookings_display(self):
        """Test that bookings are displayed correctly in month view"""
        # Create bookings in May 2026
        booking1 = Booking.objects.create(
            date=date(2026, 5, 1),
            description="May Income",
            amount=Decimal('2000.00'),
            status='booked',
            category=self.income_category
        )
        booking2 = Booking.objects.create(
            date=date(2026, 5, 15),
            description="May Expense",
            amount=Decimal('-800.00'),
            status='booked',
            category=self.expense_category
        )

        response = self.client.get(
            reverse('bookings:month_view_detail', kwargs={'year': 2026, 'month': 5})
        )

        # Check that bookings are in context
        bookings = [item['booking'] for item in response.context['bookings_with_balance']]
        self.assertEqual(len(bookings), 2)
        self.assertIn(booking1, bookings)
        self.assertIn(booking2, bookings)

    def test_month_view_running_balance(self):
        """Test that running balance is calculated correctly"""
        # Create carry forward
        Booking.objects.create(
            date=date(2026, 4, 1),
            description="April Income",
            amount=Decimal('1000.00'),
            status='booked',
            category=self.income_category
        )

        # Create bookings in May 2026
        Booking.objects.create(
            date=date(2026, 5, 1),
            description="May Income",
            amount=Decimal('2000.00'),
            status='booked',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 5, 15),
            description="May Expense",
            amount=Decimal('-500.00'),
            status='booked',
            category=self.expense_category
        )

        response = self.client.get(
            reverse('bookings:month_view_detail', kwargs={'year': 2026, 'month': 5})
        )

        bookings_with_balance = response.context['bookings_with_balance']

        # First booking: 1000 (carry forward) + 2000 = 3000
        self.assertEqual(bookings_with_balance[0]['running_balance'], Decimal('3000.00'))

        # Second booking: 3000 - 500 = 2500
        self.assertEqual(bookings_with_balance[1]['running_balance'], Decimal('2500.00'))

    def test_month_view_planned_bookings_no_running_balance(self):
        """Test that planned bookings don't affect running balance"""
        # Create booked booking
        Booking.objects.create(
            date=date(2026, 5, 1),
            description="May Income",
            amount=Decimal('2000.00'),
            status='booked',
            category=self.income_category
        )

        # Create planned booking
        Booking.objects.create(
            date=date(2026, 5, 15),
            description="Planned Expense",
            amount=Decimal('-500.00'),
            status='planned',
            category=self.expense_category
        )

        response = self.client.get(
            reverse('bookings:month_view_detail', kwargs={'year': 2026, 'month': 5})
        )

        bookings_with_balance = response.context['bookings_with_balance']

        # First booking (booked): should have running balance
        self.assertEqual(bookings_with_balance[0]['running_balance'], Decimal('2000.00'))

        # Second booking (planned): should not have running balance
        self.assertIsNone(bookings_with_balance[1]['running_balance'])

    def test_month_view_summary_calculations(self):
        """Test that month summary values are calculated correctly"""
        # Create bookings in May 2026
        Booking.objects.create(
            date=date(2026, 5, 1),
            description="Income 1",
            amount=Decimal('2000.00'),
            status='booked',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 5, 5),
            description="Income 2",
            amount=Decimal('500.00'),
            status='planned',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 5, 15),
            description="Expense 1",
            amount=Decimal('-800.00'),
            status='booked',
            category=self.expense_category
        )
        Booking.objects.create(
            date=date(2026, 5, 20),
            description="Expense 2",
            amount=Decimal('-200.00'),
            status='planned',
            category=self.expense_category
        )

        response = self.client.get(
            reverse('bookings:month_view_detail', kwargs={'year': 2026, 'month': 5})
        )

        # Month income: 2000 + 500 = 2500
        self.assertEqual(response.context['month_income'], Decimal('2500.00'))

        # Month expenses: -800 + -200 = -1000
        self.assertEqual(response.context['month_expenses'], Decimal('-1000.00'))

        # Month result: 2500 - 1000 = 1500
        self.assertEqual(response.context['month_result'], Decimal('1500.00'))

        # End balance: 0 (carry forward) + 1500 = 1500
        self.assertEqual(response.context['end_balance'], Decimal('1500.00'))

    def test_month_view_navigation(self):
        """Test that previous and next month navigation values are correct"""
        response = self.client.get(
            reverse('bookings:month_view_detail', kwargs={'year': 2026, 'month': 5})
        )

        # Previous month: April 2026
        self.assertEqual(response.context['prev_year'], 2026)
        self.assertEqual(response.context['prev_month'], 4)

        # Next month: June 2026
        self.assertEqual(response.context['next_year'], 2026)
        self.assertEqual(response.context['next_month'], 6)

    def test_month_view_navigation_year_boundary(self):
        """Test navigation across year boundaries"""
        # Test January (previous should be December of previous year)
        response = self.client.get(
            reverse('bookings:month_view_detail', kwargs={'year': 2026, 'month': 1})
        )
        self.assertEqual(response.context['prev_year'], 2025)
        self.assertEqual(response.context['prev_month'], 12)

        # Test December (next should be January of next year)
        response = self.client.get(
            reverse('bookings:month_view_detail', kwargs={'year': 2026, 'month': 12})
        )
        self.assertEqual(response.context['next_year'], 2027)
        self.assertEqual(response.context['next_month'], 1)

    def test_month_view_empty_month(self):
        """Test month view with no bookings"""
        response = self.client.get(
            reverse('bookings:month_view_detail', kwargs={'year': 2026, 'month': 5})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['bookings_with_balance']), 0)
        self.assertContains(response, 'Keine Buchungen in diesem Monat')

    def test_month_view_htmx_returns_partial(self):
        """Test that HTMX requests return only the partial template"""
        response = self.client.get(
            reverse('bookings:month_view_detail', kwargs={'year': 2026, 'month': 5}),
            HTTP_HX_REQUEST='true'
        )

        self.assertEqual(response.status_code, 200)
        # Should not contain full page elements
        self.assertNotContains(response, 'Monatsansicht')
        # Should contain month navigation
        self.assertContains(response, 'Mai 2026')

    def test_month_view_planned_carry_forward(self):
        """Test that planned carry forward includes both booked and planned bookings"""
        # Create booked bookings before May 2026
        Booking.objects.create(
            date=date(2026, 4, 1),
            description="April Income (booked)",
            amount=Decimal('1000.00'),
            status='booked',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 4, 15),
            description="April Expense (booked)",
            amount=Decimal('-500.00'),
            status='booked',
            category=self.expense_category
        )

        # Create planned bookings before May 2026
        Booking.objects.create(
            date=date(2026, 4, 20),
            description="April Income (planned)",
            amount=Decimal('300.00'),
            status='planned',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 4, 25),
            description="April Expense (planned)",
            amount=Decimal('-100.00'),
            status='planned',
            category=self.expense_category
        )

        response = self.client.get(
            reverse('bookings:month_view_detail', kwargs={'year': 2026, 'month': 5})
        )

        # Booked carry forward: 1000 - 500 = 500
        self.assertEqual(response.context['carry_forward'], Decimal('500.00'))

        # Planned carry forward: 1000 - 500 + 300 - 100 = 700
        self.assertEqual(response.context['planned_carry_forward'], Decimal('700.00'))

    def test_month_view_prev_month_cumulative_result(self):
        """Test that previous month cumulative result is calculated correctly"""
        # Create bookings before May 2026
        Booking.objects.create(
            date=date(2026, 3, 15),
            description="March Income",
            amount=Decimal('2000.00'),
            status='booked',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 3, 20),
            description="March Expense",
            amount=Decimal('-800.00'),
            status='booked',
            category=self.expense_category
        )
        Booking.objects.create(
            date=date(2026, 4, 10),
            description="April Income",
            amount=Decimal('1500.00'),
            status='booked',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 4, 15),
            description="April Expense",
            amount=Decimal('-600.00'),
            status='planned',
            category=self.expense_category
        )

        response = self.client.get(
            reverse('bookings:month_view_detail', kwargs={'year': 2026, 'month': 5})
        )

        # Previous month cumulative result (all bookings before May):
        # March: 2000 - 800 = 1200
        # April: 1500 - 600 = 900
        # Total: 1200 + 900 = 2100
        self.assertEqual(response.context['prev_month_cumulative_result'], Decimal('2100.00'))

    def test_month_view_prev_month_end_balance(self):
        """Test that previous month end balance is calculated correctly"""
        # Create bookings before May 2026
        Booking.objects.create(
            date=date(2026, 3, 15),
            description="March Income",
            amount=Decimal('3000.00'),
            status='booked',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 4, 10),
            description="April Expense",
            amount=Decimal('-1000.00'),
            status='booked',
            category=self.expense_category
        )

        response = self.client.get(
            reverse('bookings:month_view_detail', kwargs={'year': 2026, 'month': 5})
        )

        # Previous month end balance: 3000 - 1000 = 2000
        self.assertEqual(response.context['prev_month_end_balance'], Decimal('2000.00'))

    def test_month_view_cumulative_values_in_context(self):
        """Test that all new cumulative values are present in the context"""
        response = self.client.get(
            reverse('bookings:month_view_detail', kwargs={'year': 2026, 'month': 5})
        )

        self.assertEqual(response.status_code, 200)
        # Check that all new context variables exist
        self.assertIn('planned_carry_forward', response.context)
        self.assertIn('prev_month_cumulative_result', response.context)
        self.assertIn('prev_month_end_balance', response.context)

        # With no bookings, all should be zero
        self.assertEqual(response.context['planned_carry_forward'], Decimal('0.00'))
        self.assertEqual(response.context['prev_month_cumulative_result'], Decimal('0.00'))
        self.assertEqual(response.context['prev_month_end_balance'], Decimal('0.00'))


class MonthViewFilterTestCase(TestCase):
    """Test suite for the month_view row filters (date, amount, category, description)"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client = Client()
        self.client.login(username='testuser', password='testpass')

        self.income_category = Category.objects.create(
            name="Gehalt", icon="wallet", color="#28a745"
        )
        self.expense_category = Category.objects.create(
            name="Miete", icon="house", color="#dc3545"
        )

        # Carry forward booking (before the filtered month)
        Booking.objects.create(
            date=date(2026, 4, 1),
            description="April Income",
            amount=Decimal('1000.00'),
            status='booked',
            category=self.income_category
        )

        self.booking_salary = Booking.objects.create(
            date=date(2026, 5, 1),
            description="Gehalt Mai",
            amount=Decimal('2000.00'),
            status='booked',
            category=self.income_category
        )
        self.booking_rent = Booking.objects.create(
            date=date(2026, 5, 5),
            description="Miete Mai",
            amount=Decimal('-800.00'),
            status='booked',
            category=self.expense_category
        )
        self.booking_groceries = Booking.objects.create(
            date=date(2026, 5, 20),
            description="Einkauf Supermarkt",
            amount=Decimal('-50.00'),
            status='booked',
            category=self.expense_category
        )

    def _get(self, **params):
        return self.client.get(
            reverse('bookings:month_view_detail', kwargs={'year': 2026, 'month': 5}),
            params
        )

    def test_filter_by_date_range(self):
        response = self._get(date_from='2026-05-05', date_to='2026-05-31')
        bookings = [item['booking'] for item in response.context['bookings_with_balance']]
        self.assertEqual(set(bookings), {self.booking_rent, self.booking_groceries})
        self.assertTrue(response.context['is_filtered'])

    def test_filter_by_amount_range(self):
        response = self._get(amount_min='-100', amount_max='100')
        bookings = [item['booking'] for item in response.context['bookings_with_balance']]
        self.assertEqual(bookings, [self.booking_groceries])

    def test_filter_by_type_income(self):
        response = self._get(type='income')
        bookings = [item['booking'] for item in response.context['bookings_with_balance']]
        self.assertEqual(bookings, [self.booking_salary])

    def test_filter_by_type_expense(self):
        response = self._get(type='expense')
        bookings = [item['booking'] for item in response.context['bookings_with_balance']]
        self.assertEqual(set(bookings), {self.booking_rent, self.booking_groceries})

    def test_filter_by_category(self):
        response = self._get(category=self.expense_category.pk)
        bookings = [item['booking'] for item in response.context['bookings_with_balance']]
        self.assertEqual(set(bookings), {self.booking_rent, self.booking_groceries})

    def test_filter_by_description_icontains_case_insensitive(self):
        response = self._get(description='EINKAUF')
        bookings = [item['booking'] for item in response.context['bookings_with_balance']]
        self.assertEqual(bookings, [self.booking_groceries])

    def test_combined_filters_are_and_joined(self):
        response = self._get(type='expense', description='miete')
        bookings = [item['booking'] for item in response.context['bookings_with_balance']]
        self.assertEqual(bookings, [self.booking_rent])

    def test_no_filter_is_not_marked_as_filtered(self):
        response = self._get()
        self.assertFalse(response.context['is_filtered'])
        self.assertEqual(len(response.context['bookings_with_balance']), 3)

    def test_filter_does_not_change_running_balance_or_summary_bar(self):
        """Cumulative balance per row and the summary bar must reflect the full
        month regardless of the active filter."""
        unfiltered = self._get()
        filtered = self._get(type='expense')

        # Summary bar values stay identical
        for key in ('carry_forward', 'month_income', 'month_expenses', 'month_result', 'end_balance'):
            self.assertEqual(unfiltered.context[key], filtered.context[key])

        # The running balance of the visible (filtered) rows still matches
        # the value computed over the full, unfiltered month order.
        unfiltered_balances = {
            item['booking'].id: item['running_balance']
            for item in unfiltered.context['bookings_with_balance']
        }
        for item in filtered.context['bookings_with_balance']:
            self.assertEqual(item['running_balance'], unfiltered_balances[item['booking'].id])

    def test_filtered_summary_totals(self):
        response = self._get(type='expense')
        self.assertEqual(response.context['filtered_income'], Decimal('0.00'))
        self.assertEqual(response.context['filtered_expenses'], Decimal('-850.00'))
        self.assertEqual(response.context['filtered_result'], Decimal('-850.00'))

    def test_filter_empty_result_shows_dedicated_message(self):
        response = self._get(description='nonexistent-xyz')
        self.assertEqual(len(response.context['bookings_with_balance']), 0)
        self.assertContains(response, 'Keine Buchungen entsprechen dem Filter')

    def test_filters_are_preserved_across_month_navigation_links(self):
        """The prev/next month buttons must hx-include the filter form so
        active filters survive a month change."""
        response = self._get(type='expense')
        self.assertContains(response, 'hx-include="#month-filter-form"')
