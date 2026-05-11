"""
Unit tests for bookings.services
"""
from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from bookings.models import Category, Booking, RecurringSeries
from bookings.services import (
    get_current_balance,
    get_planned_income,
    get_planned_expenses,
    get_available_funds,
    get_monthly_carry_forward,
    get_bookings_for_month,
    get_due_this_month,
    get_forecast,
    get_top_categories,
    get_planned_carry_forward,
    get_previous_month_cumulative_result,
    get_previous_month_end_balance,
    get_year_overview,
)


class ServicesTestCase(TestCase):
    """Test suite for bookings services"""

    def setUp(self):
        """Set up test data"""
        # Create categories
        self.income_category = Category.objects.create(
            name="Gehalt", icon="wallet", color="#28a745"
        )
        self.expense_category = Category.objects.create(
            name="Miete", icon="house", color="#dc3545"
        )
        self.food_category = Category.objects.create(
            name="Lebensmittel", icon="cart", color="#fd7e14"
        )

    def test_get_current_balance_empty(self):
        """Test current balance with no bookings"""
        balance = get_current_balance()
        self.assertEqual(balance, Decimal('0.00'))

    def test_get_current_balance_with_bookings(self):
        """Test current balance calculation"""
        # Create some booked bookings
        Booking.objects.create(
            date=date(2026, 1, 1),
            description="Salary",
            amount=Decimal('3000.00'),
            status='booked',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 1, 5),
            description="Rent",
            amount=Decimal('-1000.00'),
            status='booked',
            category=self.expense_category
        )
        Booking.objects.create(
            date=date(2026, 1, 10),
            description="Groceries",
            amount=Decimal('-200.00'),
            status='booked',
            category=self.food_category
        )

        balance = get_current_balance()
        self.assertEqual(balance, Decimal('1800.00'))

    def test_get_current_balance_ignores_planned(self):
        """Test that current balance ignores planned bookings"""
        Booking.objects.create(
            date=date(2026, 1, 1),
            description="Salary",
            amount=Decimal('3000.00'),
            status='booked',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 2, 1),
            description="Future Salary",
            amount=Decimal('3000.00'),
            status='planned',
            category=self.income_category
        )

        balance = get_current_balance()
        self.assertEqual(balance, Decimal('3000.00'))

    def test_get_planned_income(self):
        """Test planned income calculation"""
        Booking.objects.create(
            date=date(2026, 6, 1),
            description="Salary June",
            amount=Decimal('3000.00'),
            status='planned',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 7, 1),
            description="Salary July",
            amount=Decimal('3000.00'),
            status='planned',
            category=self.income_category
        )

        income = get_planned_income()
        self.assertEqual(income, Decimal('6000.00'))

    def test_get_planned_income_with_until(self):
        """Test planned income with date limit"""
        Booking.objects.create(
            date=date(2026, 6, 1),
            description="Salary June",
            amount=Decimal('3000.00'),
            status='planned',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 7, 1),
            description="Salary July",
            amount=Decimal('3000.00'),
            status='planned',
            category=self.income_category
        )

        income = get_planned_income(until=date(2026, 6, 30))
        self.assertEqual(income, Decimal('3000.00'))

    def test_get_planned_expenses(self):
        """Test planned expenses calculation"""
        Booking.objects.create(
            date=date(2026, 6, 1),
            description="Rent",
            amount=Decimal('-1000.00'),
            status='planned',
            category=self.expense_category
        )
        Booking.objects.create(
            date=date(2026, 6, 15),
            description="Groceries",
            amount=Decimal('-200.00'),
            status='planned',
            category=self.food_category
        )

        expenses = get_planned_expenses()
        self.assertEqual(expenses, Decimal('1200.00'))  # Positive for display

    def test_get_planned_expenses_with_until(self):
        """Test planned expenses with date limit"""
        Booking.objects.create(
            date=date(2026, 6, 1),
            description="Rent June",
            amount=Decimal('-1000.00'),
            status='planned',
            category=self.expense_category
        )
        Booking.objects.create(
            date=date(2026, 7, 1),
            description="Rent July",
            amount=Decimal('-1000.00'),
            status='planned',
            category=self.expense_category
        )

        expenses = get_planned_expenses(until=date(2026, 6, 30))
        self.assertEqual(expenses, Decimal('1000.00'))

    def test_get_available_funds_no_month(self):
        """Test available funds without month scope"""
        # Current balance
        Booking.objects.create(
            date=date(2026, 1, 1),
            description="Initial",
            amount=Decimal('1000.00'),
            status='booked',
            category=self.income_category
        )

        # Planned income and expenses
        Booking.objects.create(
            date=date(2026, 6, 1),
            description="Income",
            amount=Decimal('3000.00'),
            status='planned',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 6, 5),
            description="Expense",
            amount=Decimal('-500.00'),
            status='planned',
            category=self.expense_category
        )

        funds = get_available_funds()
        self.assertEqual(funds, Decimal('3500.00'))  # 1000 + 3000 - 500

    def test_get_monthly_carry_forward(self):
        """Test carry-forward balance calculation"""
        Booking.objects.create(
            date=date(2026, 1, 15),
            description="Jan income",
            amount=Decimal('3000.00'),
            status='booked',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 1, 20),
            description="Jan expense",
            amount=Decimal('-500.00'),
            status='booked',
            category=self.expense_category
        )
        Booking.objects.create(
            date=date(2026, 2, 5),
            description="Feb income",
            amount=Decimal('3000.00'),
            status='booked',
            category=self.income_category
        )

        # Carry-forward for February should include only January
        carry_forward = get_monthly_carry_forward(2026, 2)
        self.assertEqual(carry_forward, Decimal('2500.00'))

        # Carry-forward for March should include January and February
        carry_forward = get_monthly_carry_forward(2026, 3)
        self.assertEqual(carry_forward, Decimal('5500.00'))

    def test_get_bookings_for_month(self):
        """Test getting bookings for a specific month"""
        Booking.objects.create(
            date=date(2026, 1, 31),
            description="Late Jan",
            amount=Decimal('-100.00'),
            status='booked',
            category=self.expense_category
        )
        Booking.objects.create(
            date=date(2026, 2, 1),
            description="Early Feb",
            amount=Decimal('-200.00'),
            status='planned',
            category=self.expense_category
        )
        Booking.objects.create(
            date=date(2026, 2, 15),
            description="Mid Feb",
            amount=Decimal('3000.00'),
            status='planned',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 2, 28),
            description="Late Feb",
            amount=Decimal('-300.00'),
            status='booked',
            category=self.expense_category
        )
        Booking.objects.create(
            date=date(2026, 3, 1),
            description="Early Mar",
            amount=Decimal('-400.00'),
            status='planned',
            category=self.expense_category
        )

        bookings = get_bookings_for_month(2026, 2)
        self.assertEqual(bookings.count(), 3)
        self.assertEqual(bookings[0].description, "Early Feb")
        self.assertEqual(bookings[1].description, "Mid Feb")
        self.assertEqual(bookings[2].description, "Late Feb")

    def test_get_due_this_month(self):
        """Test getting due bookings for current month"""
        today = date.today()
        last_day = date(today.year, today.month, 28)  # Safe for all months

        # Past booking (should not be included)
        Booking.objects.create(
            date=today - timedelta(days=5),
            description="Past",
            amount=Decimal('-100.00'),
            status='planned',
            category=self.expense_category
        )

        # Due this month
        Booking.objects.create(
            date=today + timedelta(days=1),
            description="Due soon",
            amount=Decimal('-200.00'),
            status='planned',
            category=self.expense_category
        )

        # Already booked (should not be included)
        Booking.objects.create(
            date=today + timedelta(days=2),
            description="Already booked",
            amount=Decimal('-300.00'),
            status='booked',
            category=self.expense_category
        )

        due = get_due_this_month()
        self.assertEqual(due.count(), 1)
        self.assertEqual(due[0].description, "Due soon")

    def test_get_forecast(self):
        """Test forecast generation"""
        # Set up current balance
        Booking.objects.create(
            date=date(2026, 1, 1),
            description="Initial",
            amount=Decimal('1000.00'),
            status='booked',
            category=self.income_category
        )

        # Add planned bookings
        today = date.today()
        Booking.objects.create(
            date=today + timedelta(days=5),
            description="Income this month",
            amount=Decimal('2000.00'),
            status='planned',
            category=self.income_category
        )
        Booking.objects.create(
            date=today + timedelta(days=10),
            description="Expense this month",
            amount=Decimal('-500.00'),
            status='planned',
            category=self.expense_category
        )

        forecast = get_forecast(months=2)

        # Should return 3 months (current + 2)
        self.assertEqual(len(forecast), 3)

        # Check structure
        for month_data in forecast:
            self.assertIn('month', month_data)
            self.assertIn('label', month_data)
            self.assertIn('projected_balance', month_data)
            self.assertIn('planned_income', month_data)
            self.assertIn('planned_expenses', month_data)

        # First month should include the planned bookings
        self.assertGreater(forecast[0]['planned_income'], Decimal('0'))

    def test_get_top_categories(self):
        """Test top categories calculation"""
        today = date.today()
        two_months_ago = today - timedelta(days=60)

        # Create expenses in different categories
        Booking.objects.create(
            date=two_months_ago,
            description="Rent 1",
            amount=Decimal('-1000.00'),
            status='booked',
            category=self.expense_category
        )
        Booking.objects.create(
            date=two_months_ago + timedelta(days=30),
            description="Rent 2",
            amount=Decimal('-1000.00'),
            status='booked',
            category=self.expense_category
        )
        Booking.objects.create(
            date=two_months_ago + timedelta(days=5),
            description="Groceries 1",
            amount=Decimal('-200.00'),
            status='booked',
            category=self.food_category
        )
        Booking.objects.create(
            date=two_months_ago + timedelta(days=15),
            description="Groceries 2",
            amount=Decimal('-150.00'),
            status='booked',
            category=self.food_category
        )

        top = get_top_categories(limit=2, months_back=3)

        # Should return rent as top category
        self.assertGreaterEqual(len(top), 1)
        self.assertEqual(top[0]['category'].name, "Miete")
        self.assertEqual(top[0]['total'], Decimal('2000.00'))

        if len(top) > 1:
            self.assertEqual(top[1]['category'].name, "Lebensmittel")

    def test_get_planned_carry_forward(self):
        """Test planned carry forward calculation includes booked and planned"""
        # Create booked booking before May 2026
        Booking.objects.create(
            date=date(2026, 4, 15),
            description="April Income",
            amount=Decimal('1000.00'),
            status='booked',
            category=self.income_category
        )
        # Create planned booking before May 2026
        Booking.objects.create(
            date=date(2026, 4, 20),
            description="April Planned Income",
            amount=Decimal('500.00'),
            status='planned',
            category=self.income_category
        )
        # Create booking in May 2026 (should not be included)
        Booking.objects.create(
            date=date(2026, 5, 1),
            description="May Income",
            amount=Decimal('2000.00'),
            status='booked',
            category=self.income_category
        )

        planned_cf = get_planned_carry_forward(2026, 5)
        self.assertEqual(planned_cf, Decimal('1500.00'))

    def test_get_planned_carry_forward_empty(self):
        """Test planned carry forward with no prior bookings"""
        planned_cf = get_planned_carry_forward(2026, 5)
        self.assertEqual(planned_cf, Decimal('0.00'))

    def test_get_previous_month_cumulative_result(self):
        """Test previous month cumulative result calculation"""
        # Create bookings before May 2026
        Booking.objects.create(
            date=date(2026, 3, 10),
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
            date=date(2026, 4, 15),
            description="April Income",
            amount=Decimal('1500.00'),
            status='planned',
            category=self.income_category
        )

        prev_result = get_previous_month_cumulative_result(2026, 5)
        # 2000 - 800 + 1500 = 2700
        self.assertEqual(prev_result, Decimal('2700.00'))

    def test_get_previous_month_cumulative_result_empty(self):
        """Test previous month cumulative result with no prior bookings"""
        prev_result = get_previous_month_cumulative_result(2026, 5)
        self.assertEqual(prev_result, Decimal('0.00'))

    def test_get_previous_month_end_balance(self):
        """Test previous month end balance calculation"""
        # Create bookings before May 2026
        Booking.objects.create(
            date=date(2026, 4, 1),
            description="April Income",
            amount=Decimal('3000.00'),
            status='booked',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 4, 15),
            description="April Expense",
            amount=Decimal('-1000.00'),
            status='booked',
            category=self.expense_category
        )

        prev_balance = get_previous_month_end_balance(2026, 5)
        # 3000 - 1000 = 2000
        self.assertEqual(prev_balance, Decimal('2000.00'))

    def test_get_previous_month_end_balance_empty(self):
        """Test previous month end balance with no prior bookings"""
        prev_balance = get_previous_month_end_balance(2026, 5)
        self.assertEqual(prev_balance, Decimal('0.00'))

    def test_new_functions_consistency(self):
        """Test that new cumulative functions work together consistently"""
        # Create bookings before May 2026
        Booking.objects.create(
            date=date(2026, 4, 1),
            description="April Booked Income",
            amount=Decimal('1000.00'),
            status='booked',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 4, 15),
            description="April Planned Expense",
            amount=Decimal('-200.00'),
            status='planned',
            category=self.expense_category
        )

        # Get all values
        booked_cf = get_monthly_carry_forward(2026, 5)
        planned_cf = get_planned_carry_forward(2026, 5)
        prev_result = get_previous_month_cumulative_result(2026, 5)
        prev_balance = get_previous_month_end_balance(2026, 5)

        # Booked carry forward should only include booked
        self.assertEqual(booked_cf, Decimal('1000.00'))

        # Planned carry forward should include both
        self.assertEqual(planned_cf, Decimal('800.00'))

        # Previous month cumulative result and end balance should be the same
        self.assertEqual(prev_result, prev_balance)
        self.assertEqual(prev_result, Decimal('800.00'))

    def test_get_year_overview_empty(self):
        """Test year overview with no bookings"""
        overview = get_year_overview(2026)
        self.assertEqual(len(overview), 12)

        # Check structure
        for month_data in overview:
            self.assertIn('month', month_data)
            self.assertIn('label', month_data)
            self.assertIn('year', month_data)
            self.assertIn('income_booked', month_data)
            self.assertIn('income_planned', month_data)
            self.assertIn('expenses_booked', month_data)
            self.assertIn('expenses_planned', month_data)
            self.assertIn('result_booked', month_data)
            self.assertIn('result_total', month_data)
            self.assertIn('booking_count', month_data)
            self.assertIn('is_future', month_data)
            self.assertIn('is_current', month_data)

        # All values should be zero with no data
        self.assertEqual(overview[0]['income_booked'], Decimal('0.00'))
        self.assertEqual(overview[0]['expenses_booked'], Decimal('0.00'))
        self.assertEqual(overview[0]['booking_count'], 0)

    def test_get_year_overview_with_bookings(self):
        """Test year overview calculates monthly data correctly"""
        # Create bookings in January
        Booking.objects.create(
            date=date(2026, 1, 10),
            description="January Income",
            amount=Decimal('3000.00'),
            status='booked',
            category=self.income_category
        )
        Booking.objects.create(
            date=date(2026, 1, 20),
            description="January Expense",
            amount=Decimal('-1500.00'),
            status='booked',
            category=self.expense_category
        )

        # Create planned booking in January
        Booking.objects.create(
            date=date(2026, 1, 25),
            description="January Planned",
            amount=Decimal('-200.00'),
            status='planned',
            category=self.expense_category
        )

        # Create bookings in February
        Booking.objects.create(
            date=date(2026, 2, 15),
            description="February Income",
            amount=Decimal('2500.00'),
            status='booked',
            category=self.income_category
        )

        overview = get_year_overview(2026)

        # Check January data
        jan = overview[0]
        self.assertEqual(jan['month'], 1)
        self.assertEqual(jan['label'], 'Januar')
        self.assertEqual(jan['income_booked'], Decimal('3000.00'))
        self.assertEqual(jan['expenses_booked'], Decimal('1500.00'))
        self.assertEqual(jan['expenses_planned'], Decimal('200.00'))
        self.assertEqual(jan['result_booked'], Decimal('1500.00'))  # 3000 - 1500
        self.assertEqual(jan['result_total'], Decimal('1300.00'))  # 3000 - 1500 - 200
        self.assertEqual(jan['booking_count'], 3)

        # Check February data
        feb = overview[1]
        self.assertEqual(feb['month'], 2)
        self.assertEqual(feb['label'], 'Februar')
        self.assertEqual(feb['income_booked'], Decimal('2500.00'))
        self.assertEqual(feb['expenses_booked'], Decimal('0.00'))
        self.assertEqual(feb['result_booked'], Decimal('2500.00'))
        self.assertEqual(feb['booking_count'], 1)

    def test_get_year_overview_is_current_flag(self):
        """Test year overview correctly identifies current month"""
        today = date.today()
        overview = get_year_overview(today.year)

        # Only current month should have is_current=True
        current_count = sum(1 for m in overview if m['is_current'])
        self.assertEqual(current_count, 1)

        # Current month should be this month
        current_month = [m for m in overview if m['is_current']][0]
        self.assertEqual(current_month['month'], today.month)

    def test_get_year_overview_is_future_flag(self):
        """Test year overview correctly identifies future months"""
        today = date.today()
        overview = get_year_overview(today.year)

        # Future months should have is_future=True
        for month_data in overview:
            first_day = date(today.year, month_data['month'], 1)
            if first_day > today:
                self.assertTrue(month_data['is_future'])
            else:
                self.assertFalse(month_data['is_future'])

    def test_get_year_overview_all_german_months(self):
        """Test year overview has correct German month names"""
        overview = get_year_overview(2026)
        expected_months = [
            'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
            'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'
        ]

        for i, month_data in enumerate(overview):
            self.assertEqual(month_data['label'], expected_months[i])

