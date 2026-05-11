"""
Unit tests for bookings.wizard
"""
from decimal import Decimal
from datetime import date
from django.test import TestCase
from bookings.models import Category, RecurringSeries, Booking
from bookings.wizard import preview_series_bookings, create_series_bookings


class WizardTestCase(TestCase):
    """Test suite for booking wizard functions"""

    def setUp(self):
        """Set up test data"""
        self.category = Category.objects.create(
            name="Miete", icon="house", color="#dc3545"
        )

    def test_preview_weekly_series(self):
        """Test preview of weekly recurring series"""
        series = RecurringSeries.objects.create(
            description="Weekly expense",
            amount=Decimal('-50.00'),
            interval='weekly',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 29),
            category=self.category
        )

        dates = preview_series_bookings(series)

        # Should generate 5 dates (Jan 1, 8, 15, 22, 29)
        self.assertEqual(len(dates), 5)
        self.assertEqual(dates[0], date(2026, 1, 1))
        self.assertEqual(dates[1], date(2026, 1, 8))
        self.assertEqual(dates[2], date(2026, 1, 15))
        self.assertEqual(dates[3], date(2026, 1, 22))
        self.assertEqual(dates[4], date(2026, 1, 29))

    def test_preview_monthly_series(self):
        """Test preview of monthly recurring series"""
        series = RecurringSeries.objects.create(
            description="Monthly rent",
            amount=Decimal('-1000.00'),
            interval='monthly',
            start_date=date(2026, 1, 15),
            end_date=date(2026, 6, 15),
            category=self.category
        )

        dates = preview_series_bookings(series)

        # Should generate 6 dates (Jan through Jun)
        self.assertEqual(len(dates), 6)
        self.assertEqual(dates[0], date(2026, 1, 15))
        self.assertEqual(dates[1], date(2026, 2, 15))
        self.assertEqual(dates[2], date(2026, 3, 15))
        self.assertEqual(dates[3], date(2026, 4, 15))
        self.assertEqual(dates[4], date(2026, 5, 15))
        self.assertEqual(dates[5], date(2026, 6, 15))

    def test_preview_monthly_series_month_end_edge_case(self):
        """Test monthly series starting on Jan 31 handles month-end correctly"""
        series = RecurringSeries.objects.create(
            description="Monthly rent",
            amount=Decimal('-1000.00'),
            interval='monthly',
            start_date=date(2026, 1, 31),
            end_date=date(2026, 4, 30),
            category=self.category
        )

        dates = preview_series_bookings(series)

        # Should handle February (28 days in 2026)
        self.assertEqual(len(dates), 4)
        self.assertEqual(dates[0], date(2026, 1, 31))
        self.assertEqual(dates[1], date(2026, 2, 28))  # Feb has only 28 days in 2026
        self.assertEqual(dates[2], date(2026, 3, 31))
        self.assertEqual(dates[3], date(2026, 4, 30))  # April has only 30 days

    def test_preview_monthly_series_leap_year(self):
        """Test monthly series handles leap year correctly"""
        series = RecurringSeries.objects.create(
            description="Monthly rent",
            amount=Decimal('-1000.00'),
            interval='monthly',
            start_date=date(2024, 1, 31),  # 2024 is a leap year
            end_date=date(2024, 3, 31),
            category=self.category
        )

        dates = preview_series_bookings(series)

        self.assertEqual(len(dates), 3)
        self.assertEqual(dates[0], date(2024, 1, 31))
        self.assertEqual(dates[1], date(2024, 2, 29))  # Feb 29 in leap year
        self.assertEqual(dates[2], date(2024, 3, 31))

    def test_preview_quarterly_series(self):
        """Test preview of quarterly recurring series"""
        series = RecurringSeries.objects.create(
            description="Quarterly payment",
            amount=Decimal('-300.00'),
            interval='quarterly',
            start_date=date(2026, 1, 15),
            end_date=date(2026, 10, 15),
            category=self.category
        )

        dates = preview_series_bookings(series)

        # Should generate 4 dates (Jan, Apr, Jul, Oct)
        self.assertEqual(len(dates), 4)
        self.assertEqual(dates[0], date(2026, 1, 15))
        self.assertEqual(dates[1], date(2026, 4, 15))
        self.assertEqual(dates[2], date(2026, 7, 15))
        self.assertEqual(dates[3], date(2026, 10, 15))

    def test_preview_yearly_series(self):
        """Test preview of yearly recurring series"""
        series = RecurringSeries.objects.create(
            description="Yearly subscription",
            amount=Decimal('-120.00'),
            interval='yearly',
            start_date=date(2026, 3, 1),
            end_date=date(2029, 3, 1),
            category=self.category
        )

        dates = preview_series_bookings(series)

        # Should generate 4 dates (2026, 2027, 2028, 2029)
        self.assertEqual(len(dates), 4)
        self.assertEqual(dates[0], date(2026, 3, 1))
        self.assertEqual(dates[1], date(2027, 3, 1))
        self.assertEqual(dates[2], date(2028, 3, 1))
        self.assertEqual(dates[3], date(2029, 3, 1))

    def test_preview_yearly_series_leap_year_edge_case(self):
        """Test yearly series handles Feb 29 correctly"""
        series = RecurringSeries.objects.create(
            description="Leap year payment",
            amount=Decimal('-100.00'),
            interval='yearly',
            start_date=date(2024, 2, 29),  # Leap year
            end_date=date(2027, 2, 28),
            category=self.category
        )

        dates = preview_series_bookings(series)

        # Should handle non-leap years
        self.assertEqual(len(dates), 4)
        self.assertEqual(dates[0], date(2024, 2, 29))
        self.assertEqual(dates[1], date(2025, 2, 28))  # 2025 is not a leap year
        self.assertEqual(dates[2], date(2026, 2, 28))  # 2026 is not a leap year
        self.assertEqual(dates[3], date(2027, 2, 28))  # 2027 is not a leap year

    def test_preview_series_no_end_date(self):
        """Test preview with no end date defaults to 2 years"""
        series = RecurringSeries.objects.create(
            description="No end",
            amount=Decimal('-100.00'),
            interval='monthly',
            start_date=date(2026, 1, 1),
            end_date=None,
            category=self.category
        )

        dates = preview_series_bookings(series)

        # Should generate 2 years worth (24 months)
        self.assertEqual(len(dates), 25)  # 24 months + starting month
        self.assertEqual(dates[0], date(2026, 1, 1))
        self.assertEqual(dates[-1], date(2028, 1, 1))

    def test_create_series_bookings(self):
        """Test creating bookings from series"""
        series = RecurringSeries.objects.create(
            description="Monthly rent",
            amount=Decimal('-1000.00'),
            interval='monthly',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 1),
            category=self.category,
            notes="Test notes"
        )

        bookings = create_series_bookings(series)

        # Should create 3 bookings
        self.assertEqual(len(bookings), 3)
        self.assertEqual(Booking.objects.filter(series=series).count(), 3)

        # Check first booking
        first = bookings[0]
        self.assertEqual(first.date, date(2026, 1, 1))
        self.assertEqual(first.description, "Monthly rent")
        self.assertEqual(first.amount, Decimal('-1000.00'))
        self.assertEqual(first.status, 'planned')
        self.assertEqual(first.category, self.category)
        self.assertEqual(first.series, series)
        self.assertEqual(first.notes, "Test notes")

    def test_create_series_bookings_idempotent(self):
        """Test that creating bookings twice doesn't create duplicates"""
        series = RecurringSeries.objects.create(
            description="Monthly rent",
            amount=Decimal('-1000.00'),
            interval='monthly',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 1),
            category=self.category
        )

        # Create bookings first time
        bookings1 = create_series_bookings(series)
        self.assertEqual(len(bookings1), 3)

        # Create bookings second time
        bookings2 = create_series_bookings(series)
        self.assertEqual(len(bookings2), 0)  # No new bookings created

        # Total should still be 3
        self.assertEqual(Booking.objects.filter(series=series).count(), 3)

    def test_create_series_bookings_partial_idempotent(self):
        """Test that creating bookings with some existing doesn't duplicate"""
        series = RecurringSeries.objects.create(
            description="Monthly rent",
            amount=Decimal('-1000.00'),
            interval='monthly',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 1),
            category=self.category
        )

        # Manually create one booking
        Booking.objects.create(
            date=date(2026, 1, 1),
            description="Monthly rent",
            amount=Decimal('-1000.00'),
            status='planned',
            category=self.category,
            series=series
        )

        # Create series bookings
        bookings = create_series_bookings(series)

        # Should only create 2 new bookings (Feb and Mar)
        self.assertEqual(len(bookings), 2)
        self.assertEqual(bookings[0].date, date(2026, 2, 1))
        self.assertEqual(bookings[1].date, date(2026, 3, 1))

        # Total should be 3
        self.assertEqual(Booking.objects.filter(series=series).count(), 3)

    def test_quarterly_year_overflow(self):
        """Test quarterly series handles year transitions"""
        series = RecurringSeries.objects.create(
            description="Quarterly payment",
            amount=Decimal('-300.00'),
            interval='quarterly',
            start_date=date(2026, 11, 1),
            end_date=date(2027, 8, 1),
            category=self.category
        )

        dates = preview_series_bookings(series)

        # Should handle year transition
        self.assertEqual(len(dates), 4)
        self.assertEqual(dates[0], date(2026, 11, 1))
        self.assertEqual(dates[1], date(2027, 2, 1))
        self.assertEqual(dates[2], date(2027, 5, 1))
        self.assertEqual(dates[3], date(2027, 8, 1))
