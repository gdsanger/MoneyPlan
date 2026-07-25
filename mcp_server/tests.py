import asyncio
from datetime import date, timedelta
from decimal import Decimal

from django.test import SimpleTestCase, TestCase, override_settings
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from alerts.models import Alert, AlertConfig
from bookings.models import Booking, Category, RecurringSeries
from timetracking.models import Client, TimeEntry

from mcp_server import logic
from mcp_server.auth import TokenAuthMiddleware
from mcp_server.resolvers import resolve_category, resolve_client
from mcp_server.server import mcp


class McpTestDataMixin:
    def setUp(self):
        self.expense_category = Category.objects.create(
            name="Miete", icon="house", color="#dc3545", category_type='expense'
        )
        self.income_category = Category.objects.create(
            name="Gehalt", icon="wallet", color="#28a745", category_type='income'
        )
        self.client_obj = Client.objects.create(name="Acme GmbH")


class CreateBookingTestCase(McpTestDataMixin, TestCase):
    def test_happy_path(self):
        result = logic.create_booking(
            date="2026-08-01", description="Miete August", amount=-950, category="Miete",
        )
        self.assertEqual(result['status'], 'planned')
        self.assertEqual(result['category'], 'Miete')
        self.assertEqual(result['amount'], '-950.00')
        self.assertTrue(Booking.objects.filter(pk=result['id']).exists())

    def test_booked_status_accepted(self):
        result = logic.create_booking(
            date="2026-08-01", description="x", amount=10, category="Gehalt", status="booked",
        )
        self.assertEqual(result['status'], 'booked')

    def test_unknown_category_raises_with_available_names(self):
        with self.assertRaises(ValueError) as ctx:
            logic.create_booking(date="2026-08-01", description="x", amount=10, category="Unbekannt")
        self.assertIn("Miete", str(ctx.exception))

    def test_zero_amount_rejected(self):
        with self.assertRaises(ValueError):
            logic.create_booking(date="2026-08-01", description="x", amount=0, category="Miete")

    def test_invalid_date_rejected(self):
        with self.assertRaises(ValueError):
            logic.create_booking(date="01.08.2026", description="x", amount=10, category="Miete")

    def test_invalid_status_rejected(self):
        with self.assertRaises(ValueError):
            logic.create_booking(date="2026-08-01", description="x", amount=10, category="Miete", status="weird")

    def test_empty_description_rejected(self):
        with self.assertRaises(ValueError):
            logic.create_booking(date="2026-08-01", description="   ", amount=10, category="Miete")

    def test_unknown_series_rejected(self):
        with self.assertRaises(ValueError):
            logic.create_booking(date="2026-08-01", description="x", amount=10, category="Miete", series_id=999)

    def test_unknown_liability_rejected(self):
        with self.assertRaises(ValueError):
            logic.create_booking(date="2026-08-01", description="x", amount=10, category="Miete", liability_id=999)


class ListPlannedBookingsTestCase(McpTestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        Booking.objects.create(
            date=date(2026, 8, 1), description="Planned 1", amount=Decimal('-100'),
            status='planned', category=self.expense_category,
        )
        Booking.objects.create(
            date=date(2026, 8, 10), description="Planned 2", amount=Decimal('-200'),
            status='planned', category=self.expense_category,
        )
        Booking.objects.create(
            date=date(2026, 8, 5), description="Booked 1", amount=Decimal('-50'),
            status='booked', category=self.expense_category,
        )

    def test_only_planned_returned(self):
        result = logic.list_planned_bookings()
        self.assertEqual(len(result), 2)
        self.assertTrue(all(b['status'] == 'planned' for b in result))

    def test_result_fields_and_order(self):
        result = logic.list_planned_bookings()
        self.assertEqual([b['description'] for b in result], ["Planned 1", "Planned 2"])
        first = result[0]
        self.assertEqual(
            set(first),
            {'id', 'date', 'description', 'amount', 'status', 'category', 'series_id', 'liability_id', 'notes'},
        )

    def test_filter_by_category_name(self):
        self.assertEqual(len(logic.list_planned_bookings(category="Miete")), 2)
        self.assertEqual(logic.list_planned_bookings(category="Gehalt"), [])

    def test_filter_by_category_id(self):
        result = logic.list_planned_bookings(category=self.expense_category.pk)
        self.assertEqual(len(result), 2)
        self.assertEqual(logic.list_planned_bookings(category=self.income_category.pk), [])

    def test_filter_by_date_range_excludes_out_of_range(self):
        self.assertEqual(logic.list_planned_bookings(date_from="2026-08-02", date_to="2026-08-09"), [])

    def test_unknown_category_filter_raises(self):
        with self.assertRaises(ValueError):
            logic.list_planned_bookings(category="Nichtvorhanden")

    def test_limit_restricts_result_count(self):
        result = logic.list_planned_bookings(limit=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['description'], "Planned 1")

    def test_zero_limit_rejected(self):
        with self.assertRaises(ValueError):
            logic.list_planned_bookings(limit=0)

    def test_invalid_limit_rejected(self):
        with self.assertRaises(ValueError):
            logic.list_planned_bookings(limit="abc")


class ListDueBookingsTestCase(McpTestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        config = AlertConfig.get()
        config.days_before_due = 3
        config.save()
        self.today = date.today()

    def _make(self, offset_days, description):
        return Booking.objects.create(
            date=self.today + timedelta(days=offset_days), description=description, amount=Decimal('-10'),
            status='planned', category=self.expense_category,
        )

    def test_overdue_and_due_soon_classified(self):
        overdue = self._make(-2, "Overdue")
        due_soon = self._make(1, "DueSoon")
        future = self._make(30, "Future")

        result = logic.list_due_bookings()
        states_by_id = {item['id']: item['due_state'] for item in result}
        self.assertEqual(states_by_id.get(overdue.id), 'overdue')
        self.assertEqual(states_by_id.get(due_soon.id), 'due_soon')
        self.assertNotIn(future.id, states_by_id)

    def test_boundary_today_is_due_soon_not_overdue(self):
        today_booking = self._make(0, "Today")
        result = logic.list_due_bookings()
        item = next(i for i in result if i['id'] == today_booking.id)
        self.assertEqual(item['due_state'], 'due_soon')
        self.assertEqual(item['days_until_due'], 0)

    def test_boundary_yesterday_is_overdue(self):
        yesterday_booking = self._make(-1, "Yesterday")
        result = logic.list_due_bookings()
        item = next(i for i in result if i['id'] == yesterday_booking.id)
        self.assertEqual(item['due_state'], 'overdue')
        self.assertEqual(item['days_until_due'], -1)

    def test_boundary_today_plus_n_is_due_soon(self):
        booking = self._make(3, "TodayPlusN")
        result = logic.list_due_bookings()
        ids = {i['id']: i for i in result}
        self.assertEqual(ids[booking.id]['due_state'], 'due_soon')
        self.assertEqual(ids[booking.id]['days_until_due'], 3)

    def test_boundary_today_plus_n_plus_1_excluded(self):
        self._make(4, "TodayPlusNPlus1")
        result = logic.list_due_bookings()
        self.assertEqual(result, [])

    def test_days_before_due_param_overrides_config(self):
        booking = self._make(4, "TodayPlusNPlus1")
        result = logic.list_due_bookings(days_before_due=4)
        ids = {i['id']: i for i in result}
        self.assertEqual(ids[booking.id]['due_state'], 'due_soon')

    def test_include_overdue_false_excludes_overdue(self):
        self._make(-2, "Overdue")
        due_soon = self._make(1, "DueSoon")
        result = logic.list_due_bookings(include_overdue=False)
        self.assertEqual([i['id'] for i in result], [due_soon.id])

    def test_include_due_soon_false_excludes_due_soon(self):
        overdue = self._make(-2, "Overdue")
        self._make(1, "DueSoon")
        result = logic.list_due_bookings(include_due_soon=False)
        self.assertEqual([i['id'] for i in result], [overdue.id])

    def test_limit_restricts_result_count(self):
        self._make(-2, "Overdue")
        self._make(1, "DueSoon")
        result = logic.list_due_bookings(limit=1)
        self.assertEqual(len(result), 1)

    def test_zero_limit_rejected(self):
        with self.assertRaises(ValueError):
            logic.list_due_bookings(limit=0)

    def test_sorted_ascending_by_date(self):
        self._make(1, "DueSoon")
        self._make(-2, "Overdue")
        result = logic.list_due_bookings()
        self.assertEqual([i['date'] for i in result], sorted(i['date'] for i in result))

    def test_read_only_does_not_create_alert_rows(self):
        Booking.objects.create(
            date=self.today - timedelta(days=1), description="Overdue", amount=Decimal('-10'),
            status='planned', category=self.expense_category,
        )
        logic.list_due_bookings()
        self.assertEqual(Alert.objects.count(), 0)

    def test_booked_entries_never_included(self):
        Booking.objects.create(
            date=self.today - timedelta(days=1), description="Booked overdue-looking", amount=Decimal('-10'),
            status='booked', category=self.expense_category,
        )
        self.assertEqual(logic.list_due_bookings(), [])


class ResolverTestCase(McpTestDataMixin, TestCase):
    def test_resolve_category_by_name_case_insensitive(self):
        self.assertEqual(resolve_category("miete").pk, self.expense_category.pk)

    def test_resolve_category_by_id(self):
        self.assertEqual(resolve_category(self.expense_category.pk).pk, self.expense_category.pk)
        self.assertEqual(resolve_category(str(self.expense_category.pk)).pk, self.expense_category.pk)

    def test_resolve_category_unknown_id_raises(self):
        with self.assertRaises(ValueError):
            resolve_category(999999)

    def test_resolve_category_not_found_lists_available(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_category("Nichtvorhanden")
        self.assertIn("Miete", str(ctx.exception))
        self.assertIn("Gehalt", str(ctx.exception))

    def test_resolve_category_empty_rejected(self):
        with self.assertRaises(ValueError):
            resolve_category("  ")

    def test_resolve_client_by_name(self):
        self.assertEqual(resolve_client("Acme GmbH").pk, self.client_obj.pk)

    def test_resolve_client_by_id(self):
        self.assertEqual(resolve_client(self.client_obj.pk).pk, self.client_obj.pk)
        self.assertEqual(resolve_client(str(self.client_obj.pk)).pk, self.client_obj.pk)

    def test_resolve_client_unknown_id_raises(self):
        with self.assertRaises(ValueError):
            resolve_client(999999)

    def test_resolve_client_not_found(self):
        with self.assertRaises(ValueError):
            resolve_client("Ghost Inc")


class ListCategoriesAndClientsTestCase(McpTestDataMixin, TestCase):
    def test_list_categories(self):
        # Migration 0007 seeds a "Neutral" category in every database, so only
        # assert that our own categories are present rather than an exact set.
        names = {c['name'] for c in logic.list_categories()}
        self.assertTrue({"Miete", "Gehalt"}.issubset(names))

    def test_list_clients(self):
        names = {c['name'] for c in logic.list_clients()}
        self.assertEqual(names, {"Acme GmbH"})


class TimeEntryTestCase(McpTestDataMixin, TestCase):
    def test_create_time_entry_happy_path(self):
        result = logic.create_time_entry(
            client="Acme GmbH", date="2026-07-01", duration=1.5, hourly_rate=100, description="Beratung",
        )
        self.assertEqual(result['duration'], '1.50')
        self.assertEqual(result['amount'], '150.00')
        self.assertFalse(result['billed'])

    def test_zero_duration_rejected(self):
        with self.assertRaises(ValueError):
            logic.create_time_entry(client="Acme GmbH", date="2026-07-01", duration=0, hourly_rate=100, description="x")

    def test_negative_rate_rejected(self):
        with self.assertRaises(ValueError):
            logic.create_time_entry(client="Acme GmbH", date="2026-07-01", duration=1, hourly_rate=-5, description="x")

    def test_unknown_client_rejected(self):
        with self.assertRaises(ValueError):
            logic.create_time_entry(client="Ghost", date="2026-07-01", duration=1, hourly_rate=10, description="x")

    def test_create_resolves_client_by_id(self):
        result = logic.create_time_entry(
            client=self.client_obj.pk, date="2026-07-01", duration=1, hourly_rate=10, description="x",
        )
        self.assertEqual(result['client'], "Acme GmbH")

    def test_empty_description_rejected(self):
        with self.assertRaises(ValueError):
            logic.create_time_entry(client="Acme GmbH", date="2026-07-01", duration=1, hourly_rate=10, description=" ")

    def test_update_partial_fields_only(self):
        entry = TimeEntry.objects.create(
            client=self.client_obj, date=date(2026, 7, 1), duration=Decimal('1.00'),
            hourly_rate=Decimal('50.00'), description="Original",
        )
        result = logic.update_time_entry(entry.id, billed=True)
        self.assertTrue(result['billed'])
        self.assertEqual(result['description'], "Original")

    def test_update_not_found_rejected(self):
        with self.assertRaises(ValueError):
            logic.update_time_entry(999999, billed=True)

    def test_update_resolves_client_by_name(self):
        other_client = Client.objects.create(name="Beta AG")
        entry = TimeEntry.objects.create(
            client=self.client_obj, date=date(2026, 7, 1), duration=Decimal('1.00'),
            hourly_rate=Decimal('50.00'), description="Original",
        )
        result = logic.update_time_entry(entry.id, client="Beta AG")
        self.assertEqual(result['client'], "Beta AG")

    def test_update_resolves_client_by_id(self):
        other_client = Client.objects.create(name="Beta AG")
        entry = TimeEntry.objects.create(
            client=self.client_obj, date=date(2026, 7, 1), duration=Decimal('1.00'),
            hourly_rate=Decimal('50.00'), description="Original",
        )
        result = logic.update_time_entry(entry.id, client=other_client.pk)
        self.assertEqual(result['client'], "Beta AG")

    def test_list_time_entries_filters(self):
        TimeEntry.objects.create(
            client=self.client_obj, date=date(2026, 7, 1), duration=Decimal('1.00'),
            hourly_rate=Decimal('50.00'), description="A", billed=True,
        )
        TimeEntry.objects.create(
            client=self.client_obj, date=date(2026, 7, 2), duration=Decimal('1.00'),
            hourly_rate=Decimal('50.00'), description="B", billed=False,
        )
        self.assertEqual(len(logic.list_time_entries(billed=True)), 1)
        self.assertEqual(len(logic.list_time_entries(billed=False)), 1)
        self.assertEqual(len(logic.list_time_entries(client="Acme GmbH")), 2)
        self.assertEqual(len(logic.list_time_entries(client=self.client_obj.pk)), 2)

    def test_list_time_entries_result_fields_and_amount(self):
        TimeEntry.objects.create(
            client=self.client_obj, date=date(2026, 7, 1), duration=Decimal('1.50'),
            hourly_rate=Decimal('100.00'), description="A",
        )
        result = logic.list_time_entries()
        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertEqual(
            set(entry),
            {'id', 'client', 'date', 'duration', 'hourly_rate', 'amount', 'description', 'notes', 'billed'},
        )
        self.assertEqual(entry['amount'], '150.00')

    def test_list_time_entries_sorted_newest_first(self):
        older = TimeEntry.objects.create(
            client=self.client_obj, date=date(2026, 7, 1), duration=Decimal('1.00'),
            hourly_rate=Decimal('50.00'), description="Older",
        )
        newer = TimeEntry.objects.create(
            client=self.client_obj, date=date(2026, 7, 2), duration=Decimal('1.00'),
            hourly_rate=Decimal('50.00'), description="Newer",
        )
        result = logic.list_time_entries()
        self.assertEqual([e['id'] for e in result], [newer.id, older.id])

    def test_list_time_entries_limit_restricts_result_count(self):
        for i in range(3):
            TimeEntry.objects.create(
                client=self.client_obj, date=date(2026, 7, 1 + i), duration=Decimal('1.00'),
                hourly_rate=Decimal('50.00'), description=f"Entry {i}",
            )
        result = logic.list_time_entries(limit=2)
        self.assertEqual(len(result), 2)

    def test_list_time_entries_zero_limit_rejected(self):
        with self.assertRaises(ValueError):
            logic.list_time_entries(limit=0)

    def test_list_time_entries_invalid_limit_rejected(self):
        with self.assertRaises(ValueError):
            logic.list_time_entries(limit="abc")

    def test_list_time_entries_unknown_client_filter_raises(self):
        with self.assertRaises(ValueError):
            logic.list_time_entries(client="Nichtvorhanden")


class RecurringSeriesTestCase(McpTestDataMixin, TestCase):
    def test_create_generates_bookings(self):
        result = logic.create_recurring_series(
            description="Miete", amount=-950, interval="monthly", start_date="2026-01-01",
            category="Miete", end_date="2026-03-01",
        )
        self.assertEqual(result['generated_bookings'], 3)
        self.assertEqual(result['booking_count'], 3)
        self.assertEqual(Booking.objects.filter(series_id=result['id']).count(), 3)

    def test_create_without_generation(self):
        result = logic.create_recurring_series(
            description="Miete", amount=-950, interval="monthly", start_date="2026-01-01",
            category="Miete", end_date="2026-03-01", generate_bookings=False,
        )
        self.assertNotIn('generated_bookings', result)
        self.assertEqual(Booking.objects.filter(series_id=result['id']).count(), 0)

    def test_invalid_interval_rejected(self):
        with self.assertRaises(ValueError):
            logic.create_recurring_series(
                description="x", amount=10, interval="daily", start_date="2026-01-01", category="Miete",
            )

    def test_end_before_start_rejected(self):
        with self.assertRaises(ValueError):
            logic.create_recurring_series(
                description="x", amount=10, interval="monthly", start_date="2026-02-01",
                category="Miete", end_date="2026-01-01",
            )

    def test_zero_amount_rejected(self):
        with self.assertRaises(ValueError):
            logic.create_recurring_series(
                description="x", amount=0, interval="monthly", start_date="2026-01-01", category="Miete",
            )

    def test_unknown_category_rejected(self):
        with self.assertRaises(ValueError):
            logic.create_recurring_series(
                description="x", amount=10, interval="monthly", start_date="2026-01-01", category="Unbekannt",
            )

    def test_list_recurring_series(self):
        RecurringSeries.objects.create(
            description="Serie1", amount=Decimal('-10'), interval='monthly',
            start_date=date(2026, 1, 1), category=self.expense_category,
        )
        self.assertEqual(len(logic.list_recurring_series()), 1)

    def test_list_recurring_series_includes_booking_count(self):
        series = RecurringSeries.objects.create(
            description="Serie1", amount=Decimal('-10'), interval='monthly',
            start_date=date(2026, 1, 1), category=self.expense_category,
        )
        Booking.objects.create(
            date=date(2026, 1, 1), description="Serie1", amount=Decimal('-10'),
            category=self.expense_category, series=series,
        )
        result = logic.list_recurring_series()
        self.assertEqual(result[0]['booking_count'], 1)

    def test_list_recurring_series_filters_by_category(self):
        RecurringSeries.objects.create(
            description="Miete", amount=Decimal('-10'), interval='monthly',
            start_date=date(2026, 1, 1), category=self.expense_category,
        )
        RecurringSeries.objects.create(
            description="Gehalt", amount=Decimal('10'), interval='monthly',
            start_date=date(2026, 1, 1), category=self.income_category,
        )
        result = logic.list_recurring_series(category="Gehalt")
        self.assertEqual([r['description'] for r in result], ["Gehalt"])

    def test_list_recurring_series_filters_by_interval(self):
        RecurringSeries.objects.create(
            description="Miete", amount=Decimal('-10'), interval='monthly',
            start_date=date(2026, 1, 1), category=self.expense_category,
        )
        RecurringSeries.objects.create(
            description="Versicherung", amount=Decimal('-100'), interval='yearly',
            start_date=date(2026, 1, 1), category=self.expense_category,
        )
        result = logic.list_recurring_series(interval="yearly")
        self.assertEqual([r['description'] for r in result], ["Versicherung"])

    def test_list_recurring_series_invalid_interval_rejected(self):
        with self.assertRaises(ValueError):
            logic.list_recurring_series(interval="daily")

    def test_list_recurring_series_respects_limit_and_order(self):
        RecurringSeries.objects.create(
            description="Aelter", amount=Decimal('-10'), interval='monthly',
            start_date=date(2026, 1, 1), category=self.expense_category,
        )
        RecurringSeries.objects.create(
            description="Neuer", amount=Decimal('-10'), interval='monthly',
            start_date=date(2026, 1, 1), category=self.expense_category,
        )
        result = logic.list_recurring_series(limit=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['description'], "Neuer")


class ServerToolRegistrationTestCase(SimpleTestCase):
    def test_all_tools_registered(self):
        tools = asyncio.run(mcp.list_tools())
        names = {t.name for t in tools}
        expected = {
            'create_booking', 'list_planned_bookings', 'list_due_bookings', 'list_categories',
            'list_clients', 'list_time_entries', 'create_time_entry', 'update_time_entry',
            'list_recurring_series', 'create_recurring_series',
        }
        self.assertEqual(names, expected)


async def _ping(request):
    return PlainTextResponse("ok")


def _auth_test_client():
    app = Starlette(routes=[Route("/ping", _ping)])
    return TestClient(TokenAuthMiddleware(app))


@override_settings(MCP_ACCESS_TOKEN="secret-token", MCP_REQUIRE_HTTPS=False)
class TokenAuthMiddlewareTestCase(SimpleTestCase):
    def test_missing_token_rejected(self):
        response = _auth_test_client().get("/ping")
        self.assertEqual(response.status_code, 401)

    def test_invalid_token_rejected(self):
        response = _auth_test_client().get("/ping?token=wrong")
        self.assertEqual(response.status_code, 401)

    def test_valid_token_via_query_string(self):
        response = _auth_test_client().get("/ping?token=secret-token")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "ok")

    def test_valid_token_via_bearer_header(self):
        response = _auth_test_client().get("/ping", headers={"Authorization": "Bearer secret-token"})
        self.assertEqual(response.status_code, 200)

    def test_no_store_header_present_on_success(self):
        response = _auth_test_client().get("/ping?token=secret-token")
        self.assertEqual(response.headers.get("cache-control"), "no-store")

    def test_no_store_header_present_on_rejection(self):
        response = _auth_test_client().get("/ping")
        self.assertEqual(response.headers.get("cache-control"), "no-store")

    @override_settings(MCP_ACCESS_TOKEN="")
    def test_unconfigured_token_rejects_everything(self):
        response = _auth_test_client().get("/ping?token=anything")
        self.assertEqual(response.status_code, 401)


@override_settings(MCP_ACCESS_TOKEN="secret-token", MCP_REQUIRE_HTTPS=True)
class TokenAuthMiddlewareHttpsTestCase(SimpleTestCase):
    def test_plain_http_rejected_when_https_required(self):
        response = _auth_test_client().get("/ping?token=secret-token")
        self.assertEqual(response.status_code, 403)

    def test_forwarded_https_header_accepted(self):
        response = _auth_test_client().get(
            "/ping?token=secret-token", headers={"X-Forwarded-Proto": "https"},
        )
        self.assertEqual(response.status_code, 200)
