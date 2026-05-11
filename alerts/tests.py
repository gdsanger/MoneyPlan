"""
Unit tests for alerts.checks
"""
from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from alerts.models import Alert, AlertConfig
from bookings.models import Category, Booking
from alerts.checks import (
    run_all_checks,
    check_due_soon,
    check_overdue,
    check_liquidity,
    cleanup_resolved_alerts,
)


class AlertChecksTestCase(TestCase):
    """Test suite for alert checking functions"""

    def setUp(self):
        """Set up test data"""
        # Create configuration
        self.config = AlertConfig.get()
        self.config.days_before_due = 3
        self.config.liquidity_threshold = Decimal('500.00')
        self.config.alert_due_enabled = True
        self.config.alert_overdue_enabled = True
        self.config.alert_liquidity_enabled = True
        self.config.save()

        # Create categories
        self.income_category = Category.objects.create(
            name="Gehalt", icon="wallet", color="#28a745"
        )
        self.expense_category = Category.objects.create(
            name="Miete", icon="house", color="#dc3545"
        )

    def test_check_due_soon_creates_alerts(self):
        """Test that due soon check creates alerts for upcoming bookings"""
        today = date.today()
        due_date = today + timedelta(days=2)

        # Create a booking due soon
        booking = Booking.objects.create(
            date=due_date,
            description="Upcoming payment",
            amount=Decimal('-500.00'),
            status='planned',
            category=self.expense_category
        )

        # Run check
        created = check_due_soon(self.config)

        # Should create 1 alert
        self.assertEqual(created, 1)

        # Verify alert exists
        alert = Alert.objects.get(alert_type='due_soon')
        self.assertEqual(alert.booking, booking)
        self.assertIn("Upcoming payment", alert.message)
        self.assertEqual(alert.dedup_key, f"due_soon_{booking.id}_{due_date}")

    def test_check_due_soon_deduplication(self):
        """Test that due soon check doesn't create duplicate alerts"""
        today = date.today()
        due_date = today + timedelta(days=2)

        # Create a booking due soon
        booking = Booking.objects.create(
            date=due_date,
            description="Upcoming payment",
            amount=Decimal('-500.00'),
            status='planned',
            category=self.expense_category
        )

        # Run check first time
        created1 = check_due_soon(self.config)
        self.assertEqual(created1, 1)

        # Run check second time
        created2 = check_due_soon(self.config)
        self.assertEqual(created2, 0)

        # Should only have 1 alert
        self.assertEqual(Alert.objects.filter(alert_type='due_soon').count(), 1)

    def test_check_due_soon_ignores_past_bookings(self):
        """Test that due soon check ignores past bookings"""
        yesterday = date.today() - timedelta(days=1)

        # Create a past booking
        Booking.objects.create(
            date=yesterday,
            description="Past payment",
            amount=Decimal('-500.00'),
            status='planned',
            category=self.expense_category
        )

        # Run check
        created = check_due_soon(self.config)

        # Should not create alert
        self.assertEqual(created, 0)

    def test_check_due_soon_ignores_far_future_bookings(self):
        """Test that due soon check ignores bookings too far in future"""
        far_future = date.today() + timedelta(days=10)

        # Create a far future booking
        Booking.objects.create(
            date=far_future,
            description="Far future payment",
            amount=Decimal('-500.00'),
            status='planned',
            category=self.expense_category
        )

        # Run check
        created = check_due_soon(self.config)

        # Should not create alert
        self.assertEqual(created, 0)

    def test_check_overdue_creates_alerts(self):
        """Test that overdue check creates alerts for overdue bookings"""
        yesterday = date.today() - timedelta(days=1)

        # Create an overdue booking
        booking = Booking.objects.create(
            date=yesterday,
            description="Overdue payment",
            amount=Decimal('-500.00'),
            status='planned',
            category=self.expense_category
        )

        # Run check
        created = check_overdue(self.config)

        # Should create 1 alert
        self.assertEqual(created, 1)

        # Verify alert exists
        alert = Alert.objects.get(alert_type='overdue')
        self.assertEqual(alert.booking, booking)
        self.assertIn("Overdue payment", alert.message)
        self.assertIn("überfällig", alert.message)
        self.assertEqual(alert.dedup_key, f"overdue_{booking.id}")

    def test_check_overdue_deduplication(self):
        """Test that overdue check doesn't create duplicate alerts"""
        yesterday = date.today() - timedelta(days=1)

        # Create an overdue booking
        Booking.objects.create(
            date=yesterday,
            description="Overdue payment",
            amount=Decimal('-500.00'),
            status='planned',
            category=self.expense_category
        )

        # Run check first time
        created1 = check_overdue(self.config)
        self.assertEqual(created1, 1)

        # Run check second time
        created2 = check_overdue(self.config)
        self.assertEqual(created2, 0)

        # Should only have 1 alert
        self.assertEqual(Alert.objects.filter(alert_type='overdue').count(), 1)

    def test_check_overdue_ignores_booked(self):
        """Test that overdue check ignores booked bookings"""
        yesterday = date.today() - timedelta(days=1)

        # Create a booked booking in the past
        Booking.objects.create(
            date=yesterday,
            description="Past booked payment",
            amount=Decimal('-500.00'),
            status='booked',
            category=self.expense_category
        )

        # Run check
        created = check_overdue(self.config)

        # Should not create alert
        self.assertEqual(created, 0)

    def test_check_liquidity_creates_alert(self):
        """Test that liquidity check creates alert when threshold is breached"""
        # Set up a scenario where balance will be low
        # Current balance is 0 (no booked bookings)
        # Add some planned expenses that will drop balance below threshold
        today = date.today()

        Booking.objects.create(
            date=today + timedelta(days=5),
            description="Large expense",
            amount=Decimal('-1000.00'),
            status='planned',
            category=self.expense_category
        )

        # Run check
        created = check_liquidity(self.config)

        # Should create 1 alert
        self.assertEqual(created, 1)

        # Verify alert exists
        alert = Alert.objects.get(alert_type='liquidity')
        self.assertIn("Liquiditätsengpass", alert.message)
        self.assertIsNone(alert.booking)  # No specific booking

    def test_check_liquidity_no_alert_when_above_threshold(self):
        """Test that liquidity check doesn't create alert when balance is healthy"""
        # Set up current balance well above threshold
        Booking.objects.create(
            date=date(2026, 1, 1),
            description="Large income",
            amount=Decimal('10000.00'),
            status='booked',
            category=self.income_category
        )

        # Run check
        created = check_liquidity(self.config)

        # Should not create alert
        self.assertEqual(created, 0)

    def test_check_liquidity_deduplication(self):
        """Test that liquidity check doesn't create duplicate alerts on same day"""
        today = date.today()

        # Create scenario with low balance
        Booking.objects.create(
            date=today + timedelta(days=5),
            description="Large expense",
            amount=Decimal('-1000.00'),
            status='planned',
            category=self.expense_category
        )

        # Run check first time
        created1 = check_liquidity(self.config)
        self.assertEqual(created1, 1)

        # Run check second time
        created2 = check_liquidity(self.config)
        self.assertEqual(created2, 0)

        # Should only have 1 alert
        self.assertEqual(Alert.objects.filter(alert_type='liquidity').count(), 1)

    def test_cleanup_resolved_alerts(self):
        """Test that cleanup removes alerts for booked bookings"""
        yesterday = date.today() - timedelta(days=1)

        # Create a planned booking with an overdue alert
        booking = Booking.objects.create(
            date=yesterday,
            description="Overdue payment",
            amount=Decimal('-500.00'),
            status='planned',
            category=self.expense_category
        )

        Alert.objects.create(
            alert_type='overdue',
            booking=booking,
            message="Test alert",
            dedup_key=f"overdue_{booking.id}"
        )

        # Verify alert exists
        self.assertEqual(Alert.objects.filter(alert_type='overdue').count(), 1)

        # Mark booking as booked
        booking.status = 'booked'
        booking.save()

        # Run cleanup
        cleaned = cleanup_resolved_alerts()

        # Should remove 1 alert
        self.assertEqual(cleaned, 1)
        self.assertEqual(Alert.objects.filter(alert_type='overdue').count(), 0)

    def test_cleanup_resolved_alerts_keeps_liquidity(self):
        """Test that cleanup keeps liquidity alerts (no specific booking)"""
        # Create a liquidity alert
        Alert.objects.create(
            alert_type='liquidity',
            booking=None,
            message="Low balance",
            dedup_key=f"liquidity_{date.today().isoformat()}"
        )

        # Run cleanup
        cleaned = cleanup_resolved_alerts()

        # Should not remove liquidity alert
        self.assertEqual(cleaned, 0)
        self.assertEqual(Alert.objects.filter(alert_type='liquidity').count(), 1)

    def test_cleanup_resolved_alerts_keeps_planned(self):
        """Test that cleanup keeps alerts for still-planned bookings"""
        yesterday = date.today() - timedelta(days=1)

        # Create a planned booking with an overdue alert
        booking = Booking.objects.create(
            date=yesterday,
            description="Still overdue",
            amount=Decimal('-500.00'),
            status='planned',
            category=self.expense_category
        )

        Alert.objects.create(
            alert_type='overdue',
            booking=booking,
            message="Test alert",
            dedup_key=f"overdue_{booking.id}"
        )

        # Run cleanup without changing booking status
        cleaned = cleanup_resolved_alerts()

        # Should not remove alert
        self.assertEqual(cleaned, 0)
        self.assertEqual(Alert.objects.filter(alert_type='overdue').count(), 1)

    def test_run_all_checks_integration(self):
        """Test run_all_checks integrates all check functions"""
        today = date.today()

        # Create various bookings
        Booking.objects.create(
            date=today + timedelta(days=2),
            description="Due soon",
            amount=Decimal('-100.00'),
            status='planned',
            category=self.expense_category
        )
        Booking.objects.create(
            date=today - timedelta(days=1),
            description="Overdue",
            amount=Decimal('-200.00'),
            status='planned',
            category=self.expense_category
        )

        # Run all checks
        summary = run_all_checks()

        # Check summary structure
        self.assertIn('created', summary)
        self.assertIn('skipped_dedup', summary)
        self.assertIn('mail_sent', summary)
        self.assertIn('errors', summary)

        # Should have created at least 2 alerts (due_soon, overdue, maybe liquidity)
        self.assertGreaterEqual(summary['created'], 2)
        self.assertEqual(summary['errors'], 0)

    def test_run_all_checks_respects_config_flags(self):
        """Test that run_all_checks respects enabled/disabled flags"""
        today = date.today()

        # Create bookings
        Booking.objects.create(
            date=today + timedelta(days=2),
            description="Due soon",
            amount=Decimal('-100.00'),
            status='planned',
            category=self.expense_category
        )
        Booking.objects.create(
            date=today - timedelta(days=1),
            description="Overdue",
            amount=Decimal('-200.00'),
            status='planned',
            category=self.expense_category
        )

        # Disable all checks
        self.config.alert_due_enabled = False
        self.config.alert_overdue_enabled = False
        self.config.alert_liquidity_enabled = False
        self.config.save()

        # Run all checks
        summary = run_all_checks()

        # Should create no alerts
        self.assertEqual(summary['created'], 0)
