"""Tests für den Minijob-Zeitnachweis."""
from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from timetracking.models import MinijobShift, MinijobSettings
from timetracking.services import get_minijob_month


class MinijobTests(TestCase):
    def setUp(self):
        User.objects.create_user('u', password='p')
        self.client.login(username='u', password='p')

    def shift(self, d, start, end, pause=0):
        return MinijobShift.objects.create(date=d, start_time=start, end_time=end, break_minutes=pause)

    def test_defaults_and_limit_hours(self):
        s = MinijobSettings.get()
        self.assertEqual(s.hourly_rate, 25)
        self.assertEqual(s.limit_hours, Decimal('12.00'))

    def test_shift_duration_with_break_and_midnight(self):
        self.assertEqual(self.shift(date(2026, 11, 2), time(9), time(13, 30), 30).minutes, 240)
        self.assertEqual(self.shift(date(2026, 11, 3), time(22), time(2)).minutes, 240)

    def test_month_within_limit(self):
        self.shift(date(2026, 11, 2), time(9), time(15))  # 6h
        d = get_minijob_month(2026, 11)
        self.assertEqual(d['total_hours'], Decimal('6.00'))
        self.assertEqual(d['over_hours'], Decimal('0.00'))
        self.assertEqual(d['covered_amount'], Decimal('150.00'))

    def test_month_over_limit(self):
        self.shift(date(2026, 11, 2), time(8), time(16))   # 8h
        self.shift(date(2026, 11, 9), time(8), time(16))   # 8h
        self.shift(date(2026, 12, 1), time(8), time(16))   # anderer Monat
        d = get_minijob_month(2026, 11)
        self.assertEqual(d['total_hours'], Decimal('16.00'))
        self.assertEqual(d['over_hours'], Decimal('4.00'))
        self.assertEqual(d['over_amount'], Decimal('100.00'))
        self.assertEqual(d['covered_amount'], Decimal('300.00'))

    def test_views(self):
        r = self.client.post(reverse('timetracking:minijob_create'), {
            'date': '2026-11-05', 'start_time': '09:00', 'end_time': '12:00',
            'break_minutes': 0, 'notes': 'Test'})
        self.assertEqual(r.status_code, 302)
        r = self.client.get(reverse('timetracking:minijob'), {'month': '2026-11'})
        self.assertContains(r, '3h 00min')
        r = self.client.get(reverse('timetracking:minijob_export'), {'month': '2026-11'})
        self.assertContains(r, '05.11.2026')
        self.assertEqual(self.client.get(reverse('timetracking:minijob_settings')).status_code, 200)
        s = MinijobShift.objects.get()
        self.assertEqual(self.client.get(reverse('timetracking:minijob_edit', args=[s.pk])).status_code, 200)
        self.client.post(reverse('timetracking:minijob_delete', args=[s.pk]))
        self.assertEqual(MinijobShift.objects.count(), 0)
