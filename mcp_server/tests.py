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
            date=date(2026, 8, 5), description="Booked 1", amount=Decimal('-50'),
            status='booked', category=self.expense_category,
        )

    def test_only_planned_returned(self):
        result = logic.list_planned_bookings()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['description'], "Planned 1")

    def test_filter_by_category(self):
        self.assertEqual(len(logic.list_planned_bookings(category="Miete")), 1)
        self.assertEqual(logic.list_planned_bookings(category="Gehalt"), [])

    def test_filter_by_date_range_excludes_out_of_range(self):
        self.assertEqual(logic.list_planned_bookings(date_from="2026-08-02"), [])

    def test_unknown_category_filter_raises(self):
        with self.assertRaises(ValueError):
            logic.list_planned_bookings(category="Nichtvorhanden")


class ListDueBookingsTestCase(McpTestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        config = AlertConfig.get()
        config.days_before_due = 3
        config.save()
        self.today = date.today()

    def test_overdue_and_due_soon_classified(self):
        overdue = Booking.objects.create(
            date=self.today - timedelta(days=2), description="Overdue", amount=Decimal('-10'),
            status='planned', category=self.expense_category,
        )
        due_soon = Booking.objects.create(
            date=self.today + timedelta(days=1), description="DueSoon", amount=Decimal('-10'),
            status='planned', category=self.expense_category,
        )
        future = Booking.objects.create(
            date=self.today + timedelta(days=30), description="Future", amount=Decimal('-10'),
            status='planned', category=self.expense_category,
        )

        result = logic.list_due_bookings()
        types_by_id = {item['id']: item['alert_type'] for item in result}
        self.assertEqual(types_by_id.get(overdue.id), 'overdue')
        self.assertEqual(types_by_id.get(due_soon.id), 'due_soon')
        self.assertNotIn(future.id, types_by_id)

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


class RecurringSeriesTestCase(McpTestDataMixin, TestCase):
    def test_create_generates_bookings(self):
        result = logic.create_recurring_series(
            description="Miete", amount=-950, interval="monthly", start_date="2026-01-01",
            category="Miete", end_date="2026-03-01",
        )
        self.assertEqual(result['generated_bookings'], 3)
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

    def test_list_recurring_series(self):
        RecurringSeries.objects.create(
            description="Serie1", amount=Decimal('-10'), interval='monthly',
            start_date=date(2026, 1, 1), category=self.expense_category,
        )
        self.assertEqual(len(logic.list_recurring_series()), 1)


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
