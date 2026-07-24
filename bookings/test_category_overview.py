from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date

from bookings.models import Booking, Category
from bookings.services import get_category_overview, get_category_bookings


class CategoryOverviewServiceTests(TestCase):
    """Aggregation logic for the category overview."""

    def setUp(self):
        self.today = date.today()
        self.income = Category.objects.create(name='Gehalt', category_type='income')
        self.expense = Category.objects.create(name='Miete', category_type='expense')
        self.neutral = Category.objects.create(name='Umbuchung', category_type='neutral')

        first = date(self.today.year, self.today.month, 1)

        # Booked bookings in the current month.
        Booking.objects.create(date=first, description='Lohn', amount=Decimal('2000.00'),
                               status='booked', category=self.income)
        Booking.objects.create(date=first, description='Wohnung', amount=Decimal('-800.00'),
                               status='booked', category=self.expense)
        # Planned booking in the current month.
        Booking.objects.create(date=first, description='Bonus', amount=Decimal('500.00'),
                               status='planned', category=self.income)
        # Booking outside the current month (previous year) — must be excluded.
        Booking.objects.create(date=date(self.today.year - 1, 1, 15), description='Alt',
                               amount=Decimal('-999.00'), status='booked', category=self.expense)

    def _month_range(self):
        from calendar import monthrange
        start = date(self.today.year, self.today.month, 1)
        end = date(self.today.year, self.today.month,
                   monthrange(self.today.year, self.today.month)[1])
        return start, end

    def test_booked_only_totals(self):
        start, end = self._month_range()
        groups = get_category_overview(start, end, include_planned=False)

        self.assertEqual(groups['income']['total'], Decimal('2000.00'))
        self.assertEqual(groups['expense']['total'], Decimal('-800.00'))
        self.assertEqual(groups['neutral']['total'], Decimal('0.00'))

    def test_include_planned_totals(self):
        start, end = self._month_range()
        groups = get_category_overview(start, end, include_planned=True)

        # 2000 booked + 500 planned
        self.assertEqual(groups['income']['total'], Decimal('2500.00'))
        self.assertEqual(groups['expense']['total'], Decimal('-800.00'))

    def test_all_categories_present_even_without_bookings(self):
        start, end = self._month_range()
        groups = get_category_overview(start, end, include_planned=False)

        # Neutral has no bookings but must still appear with total 0.
        neutral_names = [c.name for c in groups['neutral']['categories']]
        self.assertIn('Umbuchung', neutral_names)
        self.assertEqual(groups['neutral']['categories'][0].total, Decimal('0.00'))
        self.assertEqual(groups['neutral']['categories'][0].booking_count, 0)

    def test_booking_count_annotation(self):
        start, end = self._month_range()
        groups = get_category_overview(start, end, include_planned=True)
        income_cat = groups['income']['categories'][0]
        self.assertEqual(income_cat.booking_count, 2)  # Lohn + Bonus

    def test_period_excludes_out_of_range_bookings(self):
        start, end = self._month_range()
        groups = get_category_overview(start, end, include_planned=False)
        # The -999 booking from last year must not be counted.
        self.assertEqual(groups['expense']['total'], Decimal('-800.00'))

    def test_get_category_bookings_filters_status(self):
        start, end = self._month_range()
        booked = get_category_bookings(self.income, start, end, include_planned=False)
        self.assertEqual(booked.count(), 1)
        with_planned = get_category_bookings(self.income, start, end, include_planned=True)
        self.assertEqual(with_planned.count(), 2)


class CategoryOverviewViewTests(TestCase):
    """View-level behaviour for the category overview."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='u', password='p')
        self.income = Category.objects.create(name='Gehalt', category_type='income')
        self.expense = Category.objects.create(name='Miete', category_type='expense')
        first = date.today().replace(day=1)
        self.booking = Booking.objects.create(
            date=first, description='Lohn', amount=Decimal('2000.00'),
            status='booked', category=self.income,
        )

    def test_requires_login(self):
        response = self.client.get(reverse('bookings:category_overview'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

    def test_default_renders_full_page(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('bookings:category_overview'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/category_overview.html')
        self.assertContains(response, 'Gehalt')
        self.assertContains(response, 'Miete')

    def test_htmx_returns_content_partial(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('bookings:category_overview'),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/_category_overview_content.html')
        self.assertTemplateNotUsed(response, 'bookings/category_overview.html')

    def test_year_period(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('bookings:category_overview'), {'period': 'year'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['period'], 'year')
        self.assertEqual(response.context['start'], date(date.today().year, 1, 1))

    def test_custom_period_reversed_range_is_swapped(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('bookings:category_overview'), {
            'period': 'custom',
            'start': '2025-12-31',
            'end': '2025-01-01',
        })
        self.assertEqual(response.context['start'], date(2025, 1, 1))
        self.assertEqual(response.context['end'], date(2025, 12, 31))

    def test_invalid_custom_dates_fall_back_to_month(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('bookings:category_overview'), {
            'period': 'custom',
            'start': 'not-a-date',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['start'], date.today().replace(day=1))

    def test_status_all_context(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('bookings:category_overview'), {'status': 'all'}
        )
        self.assertEqual(response.context['status'], 'all')

    def test_drilldown_returns_bookings_partial(self):
        self.client.force_login(self.user)
        start = date.today().replace(day=1).isoformat()
        response = self.client.get(
            reverse('bookings:category_overview_bookings', args=[self.income.id]),
            {'period': 'month', 'status': 'booked'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/_category_overview_bookings.html')
        self.assertContains(response, 'Lohn')

    def test_drilldown_unknown_category_404(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('bookings:category_overview_bookings', args=[99999])
        )
        self.assertEqual(response.status_code, 404)
