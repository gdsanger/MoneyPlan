"""Tests for AI financial overview service and views."""
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch, Mock

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from ai.providers.base import AIResponse
from ai.exceptions import AIProviderNotConfigured
from bookings.models import Category, Booking
from dashboard.ai_overview_service import (
    build_financial_snapshot,
    generate_financial_overview,
    _format_euro,
    _response_hit_token_limit,
    _snapshot_to_prompt_text,
)
from dashboard.templatetags.dashboard_tags import render_markdown


class RenderMarkdownTest(TestCase):
    """Test Markdown rendering for financial overview output."""

    def test_renders_headings(self):
        html = render_markdown("## Gesamtlage\nAlles in Ordnung.")
        self.assertIn('<h2>Gesamtlage</h2>', html)
        self.assertIn('<p>Alles in Ordnung.</p>', html)

    def test_renders_lists(self):
        html = render_markdown("- Punkt eins\n- Punkt zwei")
        self.assertIn('<ul>', html)
        self.assertIn('<li>Punkt eins</li>', html)
        self.assertIn('<li>Punkt zwei</li>', html)

    def test_strips_unsafe_html(self):
        html = render_markdown('<script>alert("xss")</script>\n\n## Sicher')
        self.assertNotIn('<script>', html)
        self.assertIn('<h2>Sicher</h2>', html)

    def test_empty_input(self):
        self.assertEqual(render_markdown(''), '')
        self.assertEqual(render_markdown(None), '')


class FormatEuroTest(TestCase):
    """Test currency formatting helper."""

    def test_format_euro_german(self):
        self.assertEqual(_format_euro(Decimal('1234.56')), '1.234,56 €')

    def test_format_euro_zero(self):
        self.assertEqual(_format_euro(Decimal('0.00')), '0,00 €')


class BuildFinancialSnapshotTest(TestCase):
    """Test financial snapshot aggregation."""

    def setUp(self):
        self.category = Category.objects.create(
            name='Test Category',
            icon='cash',
            color='#28a745',
            category_type='income',
            description='Test Einnahmenkategorie',
        )

    def test_snapshot_with_no_data(self):
        snapshot = build_financial_snapshot()
        self.assertEqual(snapshot['current_balance'], Decimal('0.00'))
        self.assertEqual(snapshot['net_worth'], Decimal('0.00'))
        self.assertIn('today', snapshot)
        self.assertIn('forecast', snapshot)
        self.assertEqual(len(snapshot['forecast']), 4)  # current + 3 months

    def test_snapshot_with_bookings(self):
        Booking.objects.create(
            date=date.today(),
            description='Income',
            amount=Decimal('5000.00'),
            status='booked',
            category=self.category,
        )
        Booking.objects.create(
            date=date.today() + timedelta(days=10),
            description='Expense',
            amount=Decimal('-500.00'),
            status='planned',
            category=self.category,
        )

        snapshot = build_financial_snapshot()
        self.assertEqual(snapshot['current_balance'], Decimal('5000.00'))
        self.assertEqual(snapshot['planned_expenses'], Decimal('500.00'))

    def test_snapshot_to_prompt_contains_key_sections(self):
        snapshot = build_financial_snapshot()
        prompt = _snapshot_to_prompt_text(snapshot, 'short')
        self.assertIn('LIQUIDITÄT', prompt)
        self.assertIn('FORECAST', prompt)
        self.assertIn('VERMÖGEN', prompt)

    def test_snapshot_to_prompt_contains_category_reference(self):
        snapshot = build_financial_snapshot()
        prompt = _snapshot_to_prompt_text(snapshot, 'short')
        self.assertIn('KATEGORIEN (Referenz)', prompt)
        self.assertIn('Test Category (Einnahme): Test Einnahmenkategorie', prompt)


class GenerateFinancialOverviewTest(TestCase):
    """Test AI overview generation."""

    def setUp(self):
        self.category = Category.objects.create(
            name='Test Category',
            icon='cash',
            color='#28a745',
            category_type='income',
            description='Test Einnahmenkategorie',
        )

    @patch('dashboard.ai_overview_service.complete')
    def test_generate_short_overview(self, mock_complete):
        mock_complete.return_value = AIResponse(
            content="## Gesamtlage\nAlles in Ordnung.",
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=50,
            provider="openai",
        )

        result = generate_financial_overview(mode='short')

        self.assertEqual(result.mode, 'short')
        self.assertIn('Gesamtlage', result.content)
        self.assertEqual(result.ai_provider, 'openai')
        mock_complete.assert_called_once()
        call_kwargs = mock_complete.call_args[1]
        self.assertEqual(call_kwargs['feature'], 'financial_overview_short')

    @patch('dashboard.ai_overview_service.complete')
    def test_generate_detailed_overview(self, mock_complete):
        mock_complete.return_value = AIResponse(
            content="## Executive Summary\nDetaillierte Analyse.",
            model="claude-3-5-haiku-20241022",
            input_tokens=500,
            output_tokens=200,
            provider="anthropic",
        )

        result = generate_financial_overview(mode='detailed')

        self.assertEqual(result.mode, 'detailed')
        self.assertEqual(result.ai_provider, 'anthropic')
        call_kwargs = mock_complete.call_args[1]
        self.assertEqual(call_kwargs['feature'], 'financial_overview_detailed')
        self.assertEqual(call_kwargs['max_tokens'], 5000)
        self.assertIn('max. 1200 Wörter', call_kwargs['system_prompt'])

    @patch('dashboard.ai_overview_service.complete')
    def test_generate_detailed_overview_retries_when_token_limited(self, mock_complete):
        mock_complete.side_effect = [
            AIResponse(
                content="## Executive Summary\nAbgeschnittenes Wor",
                model="claude-3-5-haiku-20241022",
                input_tokens=500,
                output_tokens=5000,
                provider="anthropic",
                finish_reason="max_tokens",
            ),
            AIResponse(
                content="## Executive Summary\nVollständige Analyse.",
                model="claude-3-5-haiku-20241022",
                input_tokens=500,
                output_tokens=300,
                provider="anthropic",
                finish_reason="end_turn",
            ),
        ]

        result = generate_financial_overview(mode='detailed')

        self.assertEqual(result.content, "## Executive Summary\nVollständige Analyse.")
        self.assertEqual(mock_complete.call_count, 2)
        first_call = mock_complete.call_args_list[0][1]
        retry_call = mock_complete.call_args_list[1][1]
        self.assertEqual(first_call['max_tokens'], 5000)
        self.assertEqual(retry_call['max_tokens'], 8000)
        self.assertIn('noch kompakter', retry_call['messages'][0].content)

    def test_response_hit_token_limit_with_provider_finish_reason(self):
        response = AIResponse(
            content="Abgeschnitten",
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=5000,
            provider="openai",
            finish_reason="length",
        )

        self.assertTrue(_response_hit_token_limit(response, 5000))

    def test_response_hit_token_limit_allows_complete_response_at_limit(self):
        response = AIResponse(
            content="Vollständig.",
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=5000,
            provider="openai",
        )

        self.assertFalse(_response_hit_token_limit(response, 5000))

    @patch('dashboard.ai_overview_service.complete')
    def test_generate_raises_on_not_configured(self, mock_complete):
        mock_complete.side_effect = AIProviderNotConfigured("disabled")

        with self.assertRaises(AIProviderNotConfigured):
            generate_financial_overview(mode='short')


class FinancialOverviewViewTest(TestCase):
    """Test financial overview views."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.category = Category.objects.create(
            name='Test Category',
            icon='cash',
            color='#28a745',
            category_type='income',
            description='Test Einnahmenkategorie',
        )

    def test_overview_requires_login(self):
        response = self.client.get(reverse('dashboard:financial_overview'))
        self.assertEqual(response.status_code, 302)

    def test_overview_get_shows_form(self):
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(reverse('dashboard:financial_overview'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kurzüberblick')
        self.assertContains(response, 'Detaillierter Überblick')

    @patch('dashboard.views.generate_financial_overview')
    def test_overview_post_short(self, mock_generate):
        mock_generate.return_value = Mock(
            content="## Gesamtlage\nTest",
            mode='short',
            ai_provider='openai',
            ai_model='gpt-4o-mini',
        )

        self.client.login(username='testuser', password='testpass')
        response = self.client.post(
            reverse('dashboard:financial_overview'),
            {'mode': 'short'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kurzüberblick')
        self.assertContains(response, '<h2>Gesamtlage</h2>')
        self.assertNotContains(response, '## Gesamtlage')
        mock_generate.assert_called_once_with(mode='short')

    @patch('dashboard.views.generate_financial_overview')
    def test_overview_post_detailed(self, mock_generate):
        mock_generate.return_value = Mock(
            content="## Executive Summary\nDetail",
            mode='detailed',
            ai_provider='anthropic',
            ai_model='claude-3-5-haiku-20241022',
        )

        self.client.login(username='testuser', password='testpass')
        response = self.client.post(
            reverse('dashboard:financial_overview'),
            {'mode': 'detailed'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detaillierter Finanzüberblick')
        self.assertContains(response, '<h2>Executive Summary</h2>')
        self.assertNotContains(response, '## Executive Summary')
        mock_generate.assert_called_once_with(mode='detailed')

    @patch('dashboard.views.generate_financial_overview')
    def test_overview_post_ai_not_configured(self, mock_generate):
        mock_generate.side_effect = AIProviderNotConfigured("disabled")

        self.client.login(username='testuser', password='testpass')
        response = self.client.post(
            reverse('dashboard:financial_overview'),
            {'mode': 'short'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'KI nicht konfiguriert')

    def test_dashboard_contains_overview_button(self):
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Finanzüberblick')
        self.assertContains(response, 'overviewModal')
