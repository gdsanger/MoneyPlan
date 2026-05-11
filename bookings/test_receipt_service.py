"""Tests for receipt recognition service."""
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from bookings.receipt_service import (
    recognize_receipt,
    pdf_to_image,
    ReceiptRecognitionResult,
)
from ai.exceptions import AIResponseParseError
from ai.providers.base import AIResponse


class PDFConversionTestCase(TestCase):
    """Tests for PDF to image conversion."""

    @patch('pdf2image.convert_from_bytes')
    def test_pdf_to_image_success(self, mock_convert):
        """Test successful PDF to image conversion."""
        # Mock PIL image
        mock_image = Mock()
        mock_convert.return_value = [mock_image]

        # Mock image save
        pdf_data = b'fake pdf data'
        result = pdf_to_image(pdf_data)

        # Verify conversion was called with correct parameters
        mock_convert.assert_called_once_with(pdf_data, first_page=1, last_page=1, dpi=200)
        mock_image.save.assert_called_once()
        self.assertIsInstance(result, bytes)

    @patch('pdf2image.convert_from_bytes')
    def test_pdf_to_image_empty_pdf(self, mock_convert):
        """Test PDF with no pages raises ValueError."""
        mock_convert.return_value = []

        with self.assertRaisesMessage(ValueError, "PDF contains no pages"):
            pdf_to_image(b'fake pdf data')

    @patch('pdf2image.convert_from_bytes')
    def test_pdf_to_image_conversion_error(self, mock_convert):
        """Test PDF conversion error is wrapped in ValueError."""
        mock_convert.side_effect = Exception("Conversion failed")

        with self.assertRaisesMessage(ValueError, "Failed to convert PDF to image"):
            pdf_to_image(b'fake pdf data')


class ReceiptRecognitionTestCase(TestCase):
    """Tests for receipt recognition."""

    def setUp(self):
        """Set up test fixtures."""
        self.valid_ai_response = AIResponse(
            content='{"date": "2025-05-05", "description": "Telekom Rechnung", '
                   '"amount": -29.50, "category_suggestion": "Telekommunikation", '
                   '"notes": "Rechnungsnr. 123", '
                   '"confidence": {"date": "high", "amount": "high", "description": "medium"}, '
                   '"raw_text": "Rechnung Telekom 29.50 EUR"}',
            model='claude-3-5-haiku-20241022',
            input_tokens=100,
            output_tokens=50,
            provider='anthropic'
        )

    @patch('bookings.receipt_service.complete_with_image')
    def test_recognize_receipt_image_success(self, mock_complete):
        """Test successful receipt recognition from image."""
        mock_complete.return_value = self.valid_ai_response

        image_data = b'fake image data'
        result = recognize_receipt(image_data, 'image/jpeg')

        # Verify AI service was called
        mock_complete.assert_called_once()
        call_kwargs = mock_complete.call_args.kwargs
        self.assertEqual(call_kwargs['image_data'], image_data)
        self.assertEqual(call_kwargs['image_mime_type'], 'image/jpeg')
        self.assertEqual(call_kwargs['feature'], 'receipt_recognition')
        self.assertIn('Analysiere diesen Beleg', call_kwargs['prompt'])

        # Verify result
        self.assertIsInstance(result, ReceiptRecognitionResult)
        self.assertEqual(result.date, '2025-05-05')
        self.assertEqual(result.description, 'Telekom Rechnung')
        self.assertEqual(result.amount, Decimal('-29.50'))
        self.assertEqual(result.category_suggestion, 'Telekommunikation')
        self.assertEqual(result.notes, 'Rechnungsnr. 123')
        self.assertEqual(result.confidence['date'], 'high')
        self.assertEqual(result.ai_provider, 'anthropic')
        self.assertEqual(result.ai_model, 'claude-3-5-haiku-20241022')

    @patch('bookings.receipt_service.pdf_to_image')
    @patch('bookings.receipt_service.complete_with_image')
    def test_recognize_receipt_pdf_success(self, mock_complete, mock_pdf_to_image):
        """Test successful receipt recognition from PDF."""
        mock_complete.return_value = self.valid_ai_response
        mock_pdf_to_image.return_value = b'converted jpeg data'

        pdf_data = b'fake pdf data'
        result = recognize_receipt(pdf_data, 'application/pdf')

        # Verify PDF was converted
        mock_pdf_to_image.assert_called_once_with(pdf_data)

        # Verify AI service was called with JPEG
        mock_complete.assert_called_once()
        call_kwargs = mock_complete.call_args.kwargs
        self.assertEqual(call_kwargs['image_data'], b'converted jpeg data')
        self.assertEqual(call_kwargs['image_mime_type'], 'image/jpeg')

        # Verify result
        self.assertIsInstance(result, ReceiptRecognitionResult)

    @patch('bookings.receipt_service.complete_with_image')
    def test_recognize_receipt_json_with_markdown(self, mock_complete):
        """Test parsing JSON wrapped in markdown code blocks."""
        mock_complete.return_value = AIResponse(
            content='```json\n{"date": "2025-05-05", "description": "Test", '
                   '"amount": -10.00, "category_suggestion": "Sonstiges", '
                   '"notes": "", '
                   '"confidence": {"date": "high", "amount": "high", "description": "high"}, '
                   '"raw_text": "Test"}\n```',
            model='gpt-4o-mini',
            input_tokens=100,
            output_tokens=50,
            provider='openai'
        )

        image_data = b'fake image data'
        result = recognize_receipt(image_data, 'image/jpeg')

        # Should successfully parse despite markdown
        self.assertEqual(result.description, 'Test')
        self.assertEqual(result.amount, Decimal('-10.00'))

    @patch('bookings.receipt_service.complete_with_image')
    def test_recognize_receipt_invalid_json(self, mock_complete):
        """Test invalid JSON response raises AIResponseParseError."""
        mock_complete.return_value = AIResponse(
            content='This is not JSON',
            model='claude-3-5-haiku',
            input_tokens=100,
            output_tokens=50,
            provider='anthropic'
        )

        image_data = b'fake image data'
        with self.assertRaises(AIResponseParseError) as context:
            recognize_receipt(image_data, 'image/jpeg')

        self.assertIn('Invalid JSON', str(context.exception))

    @patch('bookings.receipt_service.complete_with_image')
    def test_recognize_receipt_missing_fields(self, mock_complete):
        """Test response with missing required fields raises AIResponseParseError."""
        mock_complete.return_value = AIResponse(
            content='{"date": "2025-05-05", "description": "Test"}',  # Missing required fields
            model='claude-3-5-haiku',
            input_tokens=100,
            output_tokens=50,
            provider='anthropic'
        )

        image_data = b'fake image data'
        with self.assertRaises(AIResponseParseError) as context:
            recognize_receipt(image_data, 'image/jpeg')

        self.assertIn('Missing required fields', str(context.exception))

    @patch('bookings.receipt_service.complete_with_image')
    def test_recognize_receipt_null_date(self, mock_complete):
        """Test receipt with null date (no date found)."""
        mock_complete.return_value = AIResponse(
            content='{"date": null, "description": "Test Receipt", '
                   '"amount": -50.00, "category_suggestion": "Sonstiges", '
                   '"notes": "", '
                   '"confidence": {"date": "low", "amount": "high", "description": "medium"}, '
                   '"raw_text": "Test Receipt 50.00"}',
            model='claude-3-5-haiku',
            input_tokens=100,
            output_tokens=50,
            provider='anthropic'
        )

        image_data = b'fake image data'
        result = recognize_receipt(image_data, 'image/jpeg')

        # Date should be None
        self.assertIsNone(result.date)
        self.assertEqual(result.confidence['date'], 'low')

    @patch('bookings.receipt_service.complete_with_image')
    def test_recognize_receipt_positive_amount(self, mock_complete):
        """Test receipt with positive amount (income/credit)."""
        mock_complete.return_value = AIResponse(
            content='{"date": "2025-05-10", "description": "Gutschrift", '
                   '"amount": 100.00, "category_suggestion": "Gehalt", '
                   '"notes": "Bonus", '
                   '"confidence": {"date": "high", "amount": "high", "description": "high"}, '
                   '"raw_text": "Gutschrift 100.00 EUR"}',
            model='gpt-4o-mini',
            input_tokens=100,
            output_tokens=50,
            provider='openai'
        )

        image_data = b'fake image data'
        result = recognize_receipt(image_data, 'image/jpeg')

        # Amount should be positive
        self.assertEqual(result.amount, Decimal('100.00'))
        self.assertTrue(result.amount > 0)
