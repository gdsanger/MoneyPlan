from decimal import Decimal
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, Client as TestClient
from django.urls import reverse

from bookings.models import Booking, Category
from timetracking.models import Client, TimeEntry
from .models import Tag
from .services import get_tag_overview


class TagOverviewServiceTests(TestCase):
    """Aggregation logic for the tag-based profitability overview."""

    def setUp(self):
        self.category_income = Category.objects.create(name='Erlöse', category_type='income')
        self.category_expense = Category.objects.create(name='Kosten', category_type='expense')
        self.project = Tag.objects.create(name='Projekt A', kind='projekt')
        self.client_tag = Tag.objects.create(name='Kunde AB', kind='kunde')
        self.time_client = Client.objects.create(name='Kunde AB')

        self.start = date(2026, 1, 1)
        self.end = date(2026, 1, 31)

    def test_booked_income_and_expenses_per_tag(self):
        income = Booking.objects.create(
            date=date(2026, 1, 10), description='Rechnung', amount=Decimal('1000.00'),
            status='booked', category=self.category_income,
        )
        income.tags.add(self.project)
        expense = Booking.objects.create(
            date=date(2026, 1, 12), description='Miete Projektraum', amount=Decimal('-300.00'),
            status='booked', category=self.category_expense,
        )
        expense.tags.add(self.project)

        overview = get_tag_overview(self.start, self.end)
        row = overview['groups']['projekt']['rows'][0]

        self.assertEqual(row['income_booked'], Decimal('1000.00'))
        self.assertEqual(row['expenses_booked'], Decimal('300.00'))
        self.assertEqual(row['result_booked'], Decimal('700.00'))

    def test_planned_and_booked_kept_separate(self):
        booked = Booking.objects.create(
            date=date(2026, 1, 5), description='Ist', amount=Decimal('500.00'),
            status='booked', category=self.category_income,
        )
        booked.tags.add(self.project)
        planned = Booking.objects.create(
            date=date(2026, 1, 20), description='Geplant', amount=Decimal('200.00'),
            status='planned', category=self.category_income,
        )
        planned.tags.add(self.project)

        overview = get_tag_overview(self.start, self.end)
        row = overview['groups']['projekt']['rows'][0]

        self.assertEqual(row['result_booked'], Decimal('500.00'))
        self.assertEqual(row['result_planned'], Decimal('200.00'))
        self.assertEqual(row['result_total'], Decimal('700.00'))

    def test_time_entries_not_double_counted_in_money_result(self):
        """
        The invoice for billed hours is booked separately as income; the time entry's
        computed value must not be added again on top of the money balance.
        """
        invoice = Booking.objects.create(
            date=date(2026, 1, 15), description='Ausgangsrechnung', amount=Decimal('450.00'),
            status='booked', category=self.category_income,
        )
        invoice.tags.add(self.project)
        entry = TimeEntry.objects.create(
            client=self.time_client, date=date(2026, 1, 14),
            duration=Decimal('3.00'), hourly_rate=Decimal('150.00'),
            description='Beratung',
        )
        entry.tags.add(self.project)

        overview = get_tag_overview(self.start, self.end)
        row = overview['groups']['projekt']['rows'][0]

        # Money result must be exactly the invoice amount, not invoice + time value.
        self.assertEqual(row['result_booked'], Decimal('450.00'))
        self.assertEqual(row['hours'], Decimal('3.00'))
        self.assertEqual(row['time_value'], Decimal('450.00'))

    def test_result_per_hour_and_revenue_per_hour(self):
        booking = Booking.objects.create(
            date=date(2026, 1, 10), description='Rechnung', amount=Decimal('600.00'),
            status='booked', category=self.category_income,
        )
        booking.tags.add(self.project)
        entry = TimeEntry.objects.create(
            client=self.time_client, date=date(2026, 1, 10),
            duration=Decimal('4.00'), hourly_rate=Decimal('100.00'),
            description='Arbeit',
        )
        entry.tags.add(self.project)

        overview = get_tag_overview(self.start, self.end)
        row = overview['groups']['projekt']['rows'][0]

        self.assertEqual(row['revenue_per_hour'], Decimal('150.00'))
        self.assertEqual(row['result_per_hour'], Decimal('150.00'))

    def test_result_per_hour_none_without_hours(self):
        booking = Booking.objects.create(
            date=date(2026, 1, 10), description='Rechnung', amount=Decimal('100.00'),
            status='booked', category=self.category_income,
        )
        booking.tags.add(self.project)

        overview = get_tag_overview(self.start, self.end)
        row = overview['groups']['projekt']['rows'][0]

        self.assertIsNone(row['revenue_per_hour'])
        self.assertIsNone(row['result_per_hour'])

    def test_untagged_bookings_and_entries_reported_separately(self):
        Booking.objects.create(
            date=date(2026, 1, 10), description='Ohne Tag', amount=Decimal('50.00'),
            status='booked', category=self.category_income,
        )
        TimeEntry.objects.create(
            client=self.time_client, date=date(2026, 1, 10),
            duration=Decimal('1.00'), hourly_rate=Decimal('80.00'),
            description='Ohne Tag',
        )

        overview = get_tag_overview(self.start, self.end)

        self.assertEqual(overview['groups'], {})
        self.assertIsNotNone(overview['untagged'])
        self.assertEqual(overview['untagged']['income_booked'], Decimal('50.00'))
        self.assertEqual(overview['untagged']['hours'], Decimal('1.00'))

    def test_no_untagged_row_when_everything_is_tagged(self):
        booking = Booking.objects.create(
            date=date(2026, 1, 10), description='Getaggt', amount=Decimal('10.00'),
            status='booked', category=self.category_income,
        )
        booking.tags.add(self.project)

        overview = get_tag_overview(self.start, self.end)
        self.assertIsNone(overview['untagged'])

    def test_dimensions_without_activity_are_omitted(self):
        booking = Booking.objects.create(
            date=date(2026, 1, 10), description='Getaggt', amount=Decimal('10.00'),
            status='booked', category=self.category_income,
        )
        booking.tags.add(self.project)

        overview = get_tag_overview(self.start, self.end)
        self.assertIn('projekt', overview['groups'])
        self.assertNotIn('kunde', overview['groups'])

    def test_out_of_range_bookings_excluded(self):
        booking = Booking.objects.create(
            date=date(2025, 12, 31), description='Vorjahr', amount=Decimal('999.00'),
            status='booked', category=self.category_income,
        )
        booking.tags.add(self.project)

        overview = get_tag_overview(self.start, self.end)
        self.assertEqual(overview['groups'], {})

    def test_grand_totals_sum_across_dimensions(self):
        project_booking = Booking.objects.create(
            date=date(2026, 1, 10), description='Projekt', amount=Decimal('100.00'),
            status='booked', category=self.category_income,
        )
        project_booking.tags.add(self.project)
        client_booking = Booking.objects.create(
            date=date(2026, 1, 11), description='Kunde', amount=Decimal('50.00'),
            status='booked', category=self.category_income,
        )
        client_booking.tags.add(self.client_tag)

        overview = get_tag_overview(self.start, self.end)
        self.assertEqual(overview['grand_totals']['income_booked'], Decimal('150.00'))
        self.assertEqual(overview['grand_totals']['result_booked'], Decimal('150.00'))

    def test_grand_totals_not_double_counted_across_dimensions(self):
        """
        A booking/time entry tagged in more than one dimension (e.g. Projekt AND
        Kunde) must still count once in the top KPIs, even though it legitimately
        shows up in both dimension rows/subtotals.
        """
        booking = Booking.objects.create(
            date=date(2026, 1, 10), description='Projekt+Kunde', amount=Decimal('100.00'),
            status='booked', category=self.category_income,
        )
        booking.tags.add(self.project, self.client_tag)
        entry = TimeEntry.objects.create(
            client=self.time_client, date=date(2026, 1, 10),
            duration=Decimal('2.00'), hourly_rate=Decimal('100.00'),
            description='Beratung',
        )
        entry.tags.add(self.project, self.client_tag)

        overview = get_tag_overview(self.start, self.end)

        # Dimension rows still show the full amount each (Epic #978).
        self.assertEqual(overview['groups']['projekt']['rows'][0]['income_booked'], Decimal('100.00'))
        self.assertEqual(overview['groups']['kunde']['rows'][0]['income_booked'], Decimal('100.00'))
        self.assertEqual(overview['groups']['projekt']['rows'][0]['hours'], Decimal('2.00'))
        self.assertEqual(overview['groups']['kunde']['rows'][0]['hours'], Decimal('2.00'))

        # But the aggregated top KPIs must count the booking/entry only once.
        self.assertEqual(overview['grand_totals']['income_booked'], Decimal('100.00'))
        self.assertEqual(overview['grand_totals']['result_booked'], Decimal('100.00'))
        self.assertEqual(overview['grand_totals']['hours'], Decimal('2.00'))
        self.assertEqual(overview['grand_totals']['time_value'], Decimal('200.00'))


class TagOverviewViewTests(TestCase):
    """View-level behaviour for the tag overview page."""

    def setUp(self):
        self.client = TestClient()
        self.user = User.objects.create_user(username='u', password='p')
        self.category_income = Category.objects.create(name='Erlöse', category_type='income')
        self.project = Tag.objects.create(name='Projekt A', kind='projekt')
        booking = Booking.objects.create(
            date=date.today().replace(day=1), description='Rechnung', amount=Decimal('100.00'),
            status='booked', category=self.category_income,
        )
        booking.tags.add(self.project)

    def test_requires_login(self):
        response = self.client.get(reverse('tags:overview'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

    def test_default_renders_full_page(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('tags:overview'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tags/tag_overview.html')
        self.assertContains(response, 'Projekt A')

    def test_htmx_returns_content_partial(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('tags:overview'), HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tags/_tag_overview_content.html')
        self.assertTemplateNotUsed(response, 'tags/tag_overview.html')

    def test_year_period(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('tags:overview'), {'period': 'year'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['period'], 'year')
        self.assertEqual(response.context['start'], date(date.today().year, 1, 1))

    def test_custom_period_reversed_range_is_swapped(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('tags:overview'), {
            'period': 'custom', 'start': '2025-12-31', 'end': '2025-01-01',
        })
        self.assertEqual(response.context['start'], date(2025, 1, 1))
        self.assertEqual(response.context['end'], date(2025, 12, 31))
