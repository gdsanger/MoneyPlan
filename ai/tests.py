"""Unit tests for AI service."""
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from ai.models import AIConfig, AIRequestLog
from ai.service import get_provider, complete, complete_with_image
from ai.providers.base import AIMessage, AIResponse
from ai.providers.openai import OpenAIProvider
from ai.providers.anthropic import AnthropicProvider
from ai.exceptions import (
    AIProviderNotConfigured,
    AIProviderUnavailable,
)


class AIConfigTestCase(TestCase):
    """Test suite for AIConfig model."""

    def test_singleton_pattern(self):
        """Test that AIConfig follows singleton pattern."""
        config1 = AIConfig.get()
        config2 = AIConfig.get()

        self.assertEqual(config1.pk, 1)
        self.assertEqual(config2.pk, 1)
        self.assertEqual(config1, config2)

    def test_default_values(self):
        """Test default configuration values."""
        config = AIConfig.get()

        self.assertEqual(config.provider, 'anthropic')
        self.assertEqual(config.max_tokens, 1000)
        self.assertTrue(config.enabled)
        self.assertEqual(config.openai_model, 'gpt-4o-mini')
        self.assertEqual(config.anthropic_model, 'claude-3-5-haiku-20241022')


class ProviderFactoryTestCase(TestCase):
    """Test suite for provider factory function."""

    def setUp(self):
        """Set up test configuration."""
        self.config = AIConfig.get()
        self.config.enabled = True
        self.config.save()

    def test_get_provider_openai(self):
        """Test getting OpenAI provider."""
        self.config.provider = 'openai'
        self.config.openai_api_key = 'test-key-123'
        self.config.save()

        provider = get_provider()

        self.assertIsInstance(provider, OpenAIProvider)
        self.assertEqual(provider.api_key, 'test-key-123')
        self.assertEqual(provider.model, 'gpt-4o-mini')

    def test_get_provider_anthropic(self):
        """Test getting Anthropic provider."""
        self.config.provider = 'anthropic'
        self.config.anthropic_api_key = 'test-key-456'
        self.config.save()

        provider = get_provider()

        self.assertIsInstance(provider, AnthropicProvider)
        self.assertEqual(provider.api_key, 'test-key-456')
        self.assertEqual(provider.model, 'claude-3-5-haiku-20241022')

    def test_get_provider_disabled(self):
        """Test that disabled service raises exception."""
        self.config.enabled = False
        self.config.save()

        with self.assertRaises(AIProviderNotConfigured) as context:
            get_provider()

        self.assertIn("disabled", str(context.exception))

    def test_get_provider_no_api_key_openai(self):
        """Test that missing OpenAI API key raises exception."""
        self.config.provider = 'openai'
        self.config.openai_api_key = ''
        self.config.save()

        with self.assertRaises(AIProviderNotConfigured) as context:
            get_provider()

        self.assertIn("OpenAI", str(context.exception))

    def test_get_provider_no_api_key_anthropic(self):
        """Test that missing Anthropic API key raises exception."""
        self.config.provider = 'anthropic'
        self.config.anthropic_api_key = ''
        self.config.save()

        with self.assertRaises(AIProviderNotConfigured) as context:
            get_provider()

        self.assertIn("Anthropic", str(context.exception))


class CompleteTestCase(TestCase):
    """Test suite for complete() function."""

    def setUp(self):
        """Set up test configuration."""
        self.config = AIConfig.get()
        self.config.provider = 'openai'
        self.config.openai_api_key = 'test-key'
        self.config.enabled = True
        self.config.max_tokens = 500
        self.config.save()

    @patch('ai.service.get_provider')
    def test_complete_success(self, mock_get_provider):
        """Test successful completion."""
        # Mock provider
        mock_provider = Mock()
        mock_response = AIResponse(
            content="Test response",
            model="gpt-4o-mini",
            input_tokens=10,
            output_tokens=20,
            provider="openai"
        )
        mock_provider.complete.return_value = mock_response
        mock_get_provider.return_value = mock_provider

        # Call complete
        messages = [AIMessage(role="user", content="Hello")]
        response = complete(messages, feature="test_feature")

        # Verify response
        self.assertEqual(response.content, "Test response")
        self.assertEqual(response.model, "gpt-4o-mini")
        self.assertEqual(response.input_tokens, 10)
        self.assertEqual(response.output_tokens, 20)

        # Verify provider was called correctly
        mock_provider.complete.assert_called_once_with(
            messages=messages,
            system_prompt="",
            max_tokens=500,
        )

        # Verify log was created
        log = AIRequestLog.objects.first()
        self.assertIsNotNone(log)
        self.assertEqual(log.provider, "openai")
        self.assertEqual(log.model, "gpt-4o-mini")
        self.assertEqual(log.feature, "test_feature")
        self.assertEqual(log.input_tokens, 10)
        self.assertEqual(log.output_tokens, 20)
        self.assertTrue(log.success)
        self.assertEqual(log.error_message, "")

    @patch('ai.service.get_provider')
    def test_complete_with_custom_max_tokens(self, mock_get_provider):
        """Test completion with custom max_tokens."""
        mock_provider = Mock()
        mock_response = AIResponse(
            content="Test",
            model="gpt-4o-mini",
            input_tokens=5,
            output_tokens=5,
            provider="openai"
        )
        mock_provider.complete.return_value = mock_response
        mock_get_provider.return_value = mock_provider

        messages = [AIMessage(role="user", content="Test")]
        complete(messages, max_tokens=2000)

        # Verify custom max_tokens was used
        mock_provider.complete.assert_called_once()
        call_kwargs = mock_provider.complete.call_args[1]
        self.assertEqual(call_kwargs['max_tokens'], 2000)

    @patch('ai.service.get_provider')
    def test_complete_failure_logs_error(self, mock_get_provider):
        """Test that failures are logged."""
        mock_provider = Mock()
        mock_provider.complete.side_effect = AIProviderUnavailable("API Error")
        mock_get_provider.return_value = mock_provider

        messages = [AIMessage(role="user", content="Test")]

        with self.assertRaises(AIProviderUnavailable):
            complete(messages, feature="test_error")

        # Verify error was logged
        log = AIRequestLog.objects.first()
        self.assertIsNotNone(log)
        self.assertEqual(log.feature, "test_error")
        self.assertFalse(log.success)
        self.assertIn("API Error", log.error_message)


class CompleteWithImageTestCase(TestCase):
    """Test suite for complete_with_image() function."""

    def setUp(self):
        """Set up test configuration."""
        self.config = AIConfig.get()
        self.config.provider = 'anthropic'
        self.config.anthropic_api_key = 'test-key'
        self.config.enabled = True
        self.config.save()

    @patch('ai.service.get_provider')
    def test_complete_with_image_success(self, mock_get_provider):
        """Test successful image completion."""
        mock_provider = Mock()
        mock_response = AIResponse(
            content="Receipt details",
            model="claude-3-5-haiku-20241022",
            input_tokens=100,
            output_tokens=50,
            provider="anthropic"
        )
        mock_provider.complete_with_image.return_value = mock_response
        mock_get_provider.return_value = mock_provider

        # Call complete_with_image
        image_data = b"fake image data"
        response = complete_with_image(
            image_data=image_data,
            image_mime_type="image/jpeg",
            prompt="Extract receipt details",
            feature="receipt_recognition"
        )

        # Verify response
        self.assertEqual(response.content, "Receipt details")
        self.assertEqual(response.provider, "anthropic")

        # Verify provider was called correctly
        mock_provider.complete_with_image.assert_called_once()

        # Verify log was created
        log = AIRequestLog.objects.first()
        self.assertIsNotNone(log)
        self.assertEqual(log.feature, "receipt_recognition")
        self.assertTrue(log.success)


class AIRequestLogTestCase(TestCase):
    """Test suite for AIRequestLog model."""

    def test_create_log_entry(self):
        """Test creating a log entry."""
        log = AIRequestLog.objects.create(
            provider="openai",
            model="gpt-4o-mini",
            feature="test",
            input_tokens=10,
            output_tokens=20,
            success=True,
            duration_ms=500
        )

        self.assertEqual(log.provider, "openai")
        self.assertEqual(log.model, "gpt-4o-mini")
        self.assertEqual(log.feature, "test")
        self.assertTrue(log.success)

    def test_log_ordering(self):
        """Test that logs are ordered by creation date (newest first)."""
        log1 = AIRequestLog.objects.create(
            provider="openai",
            model="gpt-4o-mini",
            feature="first",
            success=True
        )
        log2 = AIRequestLog.objects.create(
            provider="openai",
            model="gpt-4o-mini",
            feature="second",
            success=True
        )

        logs = list(AIRequestLog.objects.all())
        self.assertEqual(logs[0], log2)
        self.assertEqual(logs[1], log1)


class ProviderInterfaceTestCase(TestCase):
    """Test that both providers implement the required interface."""

    def test_openai_provider_interface(self):
        """Test OpenAI provider has required methods."""
        provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")

        self.assertTrue(hasattr(provider, 'complete'))
        self.assertTrue(hasattr(provider, 'complete_with_image'))
        self.assertTrue(hasattr(provider, 'test_connection'))
        self.assertTrue(callable(provider.complete))
        self.assertTrue(callable(provider.complete_with_image))
        self.assertTrue(callable(provider.test_connection))

    def test_anthropic_provider_interface(self):
        """Test Anthropic provider has required methods."""
        provider = AnthropicProvider(api_key="test", model="claude-3-5-haiku-20241022")

        self.assertTrue(hasattr(provider, 'complete'))
        self.assertTrue(hasattr(provider, 'complete_with_image'))
        self.assertTrue(hasattr(provider, 'test_connection'))
        self.assertTrue(callable(provider.complete))
        self.assertTrue(callable(provider.complete_with_image))
        self.assertTrue(callable(provider.test_connection))
