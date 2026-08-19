from decimal import Decimal
from datetime import date

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from bookings.models import Account, AccountBalance, Booking, Category
from bookings.services import (
    get_accounts_overview,
    get_snapshot_dates,
    get_snapshot_sum,
    get_latest_snapshot,
    get_account_chart_data,
)


class AccountModelTestCase(TestCase):
    def setUp(self):
        self.account = Account.objects.create(name='Giro', account_type='giro')

    def test_latest_balance_uses_most_recent_date(self):
        AccountBalance.objects.create(account=self.account, date=date(2026, 1, 1), balance=Decimal('100.00'))
        AccountBalance.objects.create(account=self.account, date=date(2026, 3, 1), balance=Decimal('250.00'))
        self.assertEqual(self.account.latest_balance, Decimal('250.00'))
        self.assertEqual(self.account.latest_balance_entry.date, date(2026, 3, 1))

    def test_latest_balance_none_without_entries(self):
        self.assertIsNone(self.account.latest_balance)

    def test_unique_account_and_date(self):
        from django.db.utils import IntegrityError
        AccountBalance.objects.create(account=self.account, date=date(2026, 1, 1), balance=Decimal('100.00'))
        with self.assertRaises(IntegrityError):
            AccountBalance.objects.create(account=self.account, date=date(2026, 1, 1), balance=Decimal('200.00'))


class AccountServicesTestCase(TestCase):
    def setUp(self):
        self.giro = Account.objects.create(name='Giro', account_type='giro', sort_order=1)
        self.cash = Account.objects.create(name='Bargeld', account_type='cash', sort_order=2)
        self.inactive = Account.objects.create(name='Alt', account_type='other', is_active=False, sort_order=3)

        AccountBalance.objects.create(account=self.giro, date=date(2026, 1, 1), balance=Decimal('1000.00'))
        AccountBalance.objects.create(account=self.giro, date=date(2026, 2, 1), balance=Decimal('1200.00'))
        AccountBalance.objects.create(account=self.cash, date=date(2026, 2, 1), balance=Decimal('50.00'))
        AccountBalance.objects.create(account=self.inactive, date=date(2026, 2, 1), balance=Decimal('999.00'))

    def test_overview_excludes_inactive_by_default(self):
        overview = get_accounts_overview()
        names = {row['account'].name for row in overview}
        self.assertEqual(names, {'Giro', 'Bargeld'})

    def test_overview_latest_balance(self):
        overview = {row['account'].name: row for row in get_accounts_overview()}
        self.assertEqual(overview['Giro']['latest_balance'], Decimal('1200.00'))
        self.assertEqual(overview['Giro']['latest_date'], date(2026, 2, 1))

    def test_snapshot_dates_sorted_desc(self):
        self.assertEqual(get_snapshot_dates(), [date(2026, 2, 1), date(2026, 1, 1)])

    def test_snapshot_sum_only_that_date(self):
        # 2026-02-01: giro 1200 + cash 50 + inactive 999
        self.assertEqual(get_snapshot_sum(date(2026, 2, 1)), Decimal('2249.00'))
        # 2026-01-01: only giro 1000
        self.assertEqual(get_snapshot_sum(date(2026, 1, 1)), Decimal('1000.00'))

    def test_latest_snapshot(self):
        snap = get_latest_snapshot()
        self.assertEqual(snap['date'], date(2026, 2, 1))
        self.assertEqual(snap['sum'], Decimal('2249.00'))

    def test_chart_data_carry_forward_and_total(self):
        data = get_account_chart_data()
        self.assertEqual(data['labels'], ['2026-01-01', '2026-02-01'])
        # Total on 2026-01-01: only giro known (1000). cash/inactive not yet -> excluded.
        self.assertEqual(data['total'][0], 1000.0)
        # Total on 2026-02-01: giro 1200 + cash 50 + inactive 999 = 2249
        self.assertEqual(data['total'][1], 2249.0)

    def test_chart_data_empty(self):
        AccountBalance.objects.all().delete()
        data = get_account_chart_data()
        self.assertEqual(data, {'labels': [], 'accounts': [], 'total': []})


class AccountViewTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='u', password='p')
        self.client.login(username='u', password='p')
        self.giro = Account.objects.create(name='Giro', account_type='giro')
        self.cash = Account.objects.create(name='Bargeld', account_type='cash')

    def test_overview_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('bookings:account_overview'))
        self.assertEqual(response.status_code, 302)

    def test_overview_total_sums_latest_balances(self):
        AccountBalance.objects.create(account=self.giro, date=date(2026, 1, 1), balance=Decimal('100.00'))
        AccountBalance.objects.create(account=self.giro, date=date(2026, 2, 1), balance=Decimal('300.00'))
        AccountBalance.objects.create(account=self.cash, date=date(2026, 2, 1), balance=Decimal('40.00'))
        response = self.client.get(reverse('bookings:account_overview'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total'], Decimal('340.00'))

    def test_create_account(self):
        response = self.client.post(reverse('bookings:account_create'), {
            'name': 'PayPal', 'account_type': 'paypal', 'sort_order': 0, 'is_active': 'on',
        })
        self.assertRedirects(response, reverse('bookings:account_overview'))
        self.assertTrue(Account.objects.filter(name='PayPal').exists())

    def test_snapshot_creates_and_updates(self):
        # First snapshot: create balances for both accounts on a date
        response = self.client.post(reverse('bookings:account_snapshot'), {
            'date': '2026-05-01',
            f'balance_{self.giro.pk}': '500.00',
            f'balance_{self.cash.pk}': '30.00',
        })
        self.assertRedirects(response, reverse('bookings:account_overview'))
        self.assertEqual(AccountBalance.objects.count(), 2)

        # Second snapshot same date: update giro, no duplicates
        self.client.post(reverse('bookings:account_snapshot'), {
            'date': '2026-05-01',
            f'balance_{self.giro.pk}': '600.00',
            f'balance_{self.cash.pk}': '30.00',
        })
        self.assertEqual(AccountBalance.objects.count(), 2)
        giro_balance = AccountBalance.objects.get(account=self.giro, date=date(2026, 5, 1))
        self.assertEqual(giro_balance.balance, Decimal('600.00'))

    def test_snapshot_empty_field_removes_existing(self):
        AccountBalance.objects.create(account=self.giro, date=date(2026, 5, 1), balance=Decimal('500.00'))
        self.client.post(reverse('bookings:account_snapshot'), {
            'date': '2026-05-01',
            f'balance_{self.giro.pk}': '',
            f'balance_{self.cash.pk}': '',
        })
        self.assertFalse(AccountBalance.objects.filter(account=self.giro, date=date(2026, 5, 1)).exists())

    def test_balance_edit_and_delete(self):
        balance = AccountBalance.objects.create(account=self.giro, date=date(2026, 5, 1), balance=Decimal('500.00'))
        # edit
        response = self.client.post(reverse('bookings:account_balance_edit', args=[balance.pk]), {
            'account': self.giro.pk, 'date': '2026-05-01', 'balance': '550.00', 'note': 'Korrektur',
        })
        self.assertRedirects(response, reverse('bookings:account_detail', args=[self.giro.pk]))
        balance.refresh_from_db()
        self.assertEqual(balance.balance, Decimal('550.00'))
        # delete
        response = self.client.post(reverse('bookings:account_balance_delete', args=[balance.pk]))
        self.assertRedirects(response, reverse('bookings:account_detail', args=[self.giro.pk]))
        self.assertFalse(AccountBalance.objects.filter(pk=balance.pk).exists())

    def test_account_delete_cascades_balances(self):
        AccountBalance.objects.create(account=self.giro, date=date(2026, 5, 1), balance=Decimal('500.00'))
        self.client.post(reverse('bookings:account_delete', args=[self.giro.pk]))
        self.assertFalse(Account.objects.filter(pk=self.giro.pk).exists())
        self.assertEqual(AccountBalance.objects.filter(account_id=self.giro.pk).count(), 0)


class ReconciliationSnapshotPrefillTestCase(TestCase):
    """The reconciliation view should prefill the Ist-Gesamtstand from the latest snapshot."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='u', password='p')
        self.client.login(username='u', password='p')
        Category.objects.get(category_type='neutral')  # seeded by migration 0007
        self.giro = Account.objects.create(name='Giro')

    def test_prefill_from_latest_snapshot(self):
        AccountBalance.objects.create(account=self.giro, date=date(2026, 6, 1), balance=Decimal('1234.56'))
        response = self.client.get(reverse('bookings:reconciliation'))
        self.assertEqual(response.context['actual_balance'], Decimal('1234.56'))
        self.assertEqual(response.context['latest_snapshot']['sum'], Decimal('1234.56'))

    def test_explicit_query_param_overrides_prefill(self):
        AccountBalance.objects.create(account=self.giro, date=date(2026, 6, 1), balance=Decimal('1234.56'))
        response = self.client.get(reverse('bookings:reconciliation'), {'actual_balance': '2000.00'})
        self.assertEqual(response.context['actual_balance'], Decimal('2000.00'))

    def test_no_snapshot_no_prefill(self):
        response = self.client.get(reverse('bookings:reconciliation'))
        self.assertIsNone(response.context['actual_balance'])
