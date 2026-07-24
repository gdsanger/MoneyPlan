"""Tests for receipt upload views."""
from decimal import Decimal
from unittest.mock import patch, Mock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from bookings.models import Booking, Category
from bookings.receipt_service import ReceiptRecognitionResult
from ai.exceptions import AIProviderNotConfigured


class ReceiptUploadViewTestCase(TestCase):
    """Tests for receipt upload views."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')

        # Create test category
        self.category = Category.objects.create(
            name='Telekommunikation',
            icon='bi-phone',
            color='#0066cc'
        )

    def test_receipt_upload_get(self):
        """Test GET request returns upload form."""
        response = self.client.get(reverse('bookings:receipt_upload'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Beleg hochladen')
        self.assertContains(response, 'receipt_file')

    @patch('bookings.views.magic.from_buffer')
    @patch('bookings.views.recognize_receipt')
    def test_receipt_upload_post_success(self, mock_recognize, mock_magic):
        """Test POST with valid image file."""
        # Mock MIME type detection
        mock_magic.return_value = 'image/jpeg'

        # Mock recognition result
        mock_recognize.return_value = ReceiptRecognitionResult(
            date='2025-05-05',
            description='Telekom Rechnung',
            amount=Decimal('-29.50'),
            category_suggestion='Telekommunikation',
            notes='Rechnungsnr. 123',
            confidence={'date': 'high', 'amount': 'high', 'description': 'medium'},
            raw_text='Rechnung Telekom 29.50 EUR',
            ai_provider='anthropic',
            ai_model='claude-3-5-haiku-20241022'
        )

        # Create fake image file
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile

        image_data = b'fake image data'
        image_file = SimpleUploadedFile(
            name='receipt.jpg',
            content=image_data,
            content_type='image/jpeg'
        )

        response = self.client.post(
            reverse('bookings:receipt_upload'),
            {'receipt_file': image_file},
            HTTP_HX_REQUEST='true'
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Beleg erkannt')
        self.assertContains(response, 'Telekom Rechnung')
        self.assertContains(response, '-29')
        self.assertContains(response, 'anthropic')

        # Check session data
        self.assertIn('receipt_result', self.client.session)
        self.assertIn('receipt_file_data', self.client.session)

    def test_receipt_upload_no_file(self):
        """Test POST without file returns error."""
        response = self.client.post(
            reverse('bookings:receipt_upload'),
            {},
            HTTP_HX_REQUEST='true'
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Keine Datei ausgewählt')

    @patch('bookings.views.magic.from_buffer')
    @patch('bookings.views.recognize_receipt')
    def test_receipt_upload_ai_not_configured(self, mock_recognize, mock_magic):
        """Test POST when AI is not configured."""
        mock_magic.return_value = 'image/jpeg'
        mock_recognize.side_effect = AIProviderNotConfigured("AI service is disabled")

        from django.core.files.uploadedfile import SimpleUploadedFile
        image_file = SimpleUploadedFile(
            name='receipt.jpg',
            content=b'fake image data',
            content_type='image/jpeg'
        )

        response = self.client.post(
            reverse('bookings:receipt_upload'),
            {'receipt_file': image_file},
            HTTP_HX_REQUEST='true'
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'KI nicht konfiguriert')

    @patch('bookings.views.magic.from_buffer')
    @patch('bookings.views.recognize_receipt')
    def test_receipt_confirm_success(self, mock_recognize, mock_magic):
        """Test confirming and saving a booking from receipt."""
        mock_magic.return_value = 'image/jpeg'

        # First, upload a receipt to populate session
        mock_recognize.return_value = ReceiptRecognitionResult(
            date='2025-05-05',
            description='Test Receipt',
            amount=Decimal('-50.00'),
            category_suggestion='Telekommunikation',
            notes='Test notes',
            confidence={'date': 'high', 'amount': 'high', 'description': 'high'},
            raw_text='Test receipt text',
            ai_provider='openai',
            ai_model='gpt-4o-mini'
        )

        from django.core.files.uploadedfile import SimpleUploadedFile
        image_file = SimpleUploadedFile(
            name='receipt.jpg',
            content=b'fake image data',
            content_type='image/jpeg'
        )

        # Upload receipt
        self.client.post(
            reverse('bookings:receipt_upload'),
            {'receipt_file': image_file},
            HTTP_HX_REQUEST='true'
        )

        # Now confirm and create booking
        response = self.client.post(
            reverse('bookings:receipt_confirm'),
            {
                'date': '2025-05-05',
                'description': 'Test Receipt',
                'amount': '-50.00',
                'category': self.category.id,
                'status': 'planned',
                'notes': 'Test notes',
            },
            HTTP_HX_REQUEST='true'
        )

        # Should redirect
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['HX-Redirect'], '/bookings/')

        # Check booking was created
        booking = Booking.objects.get(description='Test Receipt')
        self.assertEqual(booking.amount, Decimal('-50.00'))
        self.assertEqual(booking.category, self.category)
        self.assertEqual(booking.status, 'planned')

        # Check session was cleared
        self.assertNotIn('receipt_result', self.client.session)

    def test_receipt_confirm_no_session_data(self):
        """Test confirm without session data returns error."""
        response = self.client.post(
            reverse('bookings:receipt_confirm'),
            {
                'date': '2025-05-05',
                'description': 'Test',
                'amount': '-50.00',
                'category': self.category.id,
                'status': 'planned',
            },
            HTTP_HX_REQUEST='true'
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Session abgelaufen')

    def test_receipt_upload_requires_login(self):
        """Test receipt upload requires authentication."""
        self.client.logout()

        response = self.client.get(reverse('bookings:receipt_upload'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        self.assertIn('/accounts/login/', response.url)

    def test_receipt_upload_get_with_month_context_renders_hidden_fields(self):
        """Test that opening from the month view carries the return month through."""
        response = self.client.get(
            reverse('bookings:receipt_upload'), {'return_year': '2025', 'return_month': '5'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="return_year" value="2025"')
        self.assertContains(response, 'name="return_month" value="5"')

    @patch('bookings.views.magic.from_buffer')
    @patch('bookings.views.recognize_receipt')
    def test_receipt_confirm_from_month_view_same_month(self, mock_recognize, mock_magic):
        """Test confirming from month view reloads the month instead of redirecting."""
        mock_magic.return_value = 'image/jpeg'
        mock_recognize.return_value = ReceiptRecognitionResult(
            date='2025-05-05',
            description='Test Receipt',
            amount=Decimal('-50.00'),
            category_suggestion='Telekommunikation',
            notes='Test notes',
            confidence={'date': 'high', 'amount': 'high', 'description': 'high'},
            raw_text='Test receipt text',
            ai_provider='openai',
            ai_model='gpt-4o-mini'
        )

        from django.core.files.uploadedfile import SimpleUploadedFile
        image_file = SimpleUploadedFile(
            name='receipt.jpg', content=b'fake image data', content_type='image/jpeg'
        )

        self.client.post(
            reverse('bookings:receipt_upload'),
            {'receipt_file': image_file, 'return_year': '2025', 'return_month': '5'},
            HTTP_HX_REQUEST='true'
        )

        response = self.client.post(
            reverse('bookings:receipt_confirm'),
            {
                'date': '2025-05-05',
                'description': 'Test Receipt',
                'amount': '-50.00',
                'category': self.category.id,
                'status': 'planned',
                'notes': 'Test notes',
                'return_year': '2025',
                'return_month': '5',
            },
            HTTP_HX_REQUEST='true'
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('HX-Redirect', response)
        self.assertEqual(response['HX-Trigger'], 'receiptBookingSaved')
        self.assertContains(response, 'wurde erstellt')
        self.assertTrue(Booking.objects.filter(description='Test Receipt').exists())

    @patch('bookings.views.magic.from_buffer')
    @patch('bookings.views.recognize_receipt')
    def test_receipt_confirm_from_month_view_different_month(self, mock_recognize, mock_magic):
        """Test that a receipt dated outside the displayed month gives a clear notice, not HX-Trigger reload."""
        mock_magic.return_value = 'image/jpeg'
        mock_recognize.return_value = ReceiptRecognitionResult(
            date='2025-05-05',
            description='Other Month Receipt',
            amount=Decimal('-20.00'),
            category_suggestion='Telekommunikation',
            notes='',
            confidence={'date': 'high', 'amount': 'high', 'description': 'high'},
            raw_text='Test receipt text',
            ai_provider='openai',
            ai_model='gpt-4o-mini'
        )

        from django.core.files.uploadedfile import SimpleUploadedFile
        image_file = SimpleUploadedFile(
            name='receipt.jpg', content=b'fake image data', content_type='image/jpeg'
        )

        # Opened from June 2025 month view, but the receipt is dated in May 2025
        self.client.post(
            reverse('bookings:receipt_upload'),
            {'receipt_file': image_file, 'return_year': '2025', 'return_month': '6'},
            HTTP_HX_REQUEST='true'
        )

        response = self.client.post(
            reverse('bookings:receipt_confirm'),
            {
                'date': '2025-05-05',
                'description': 'Other Month Receipt',
                'amount': '-20.00',
                'category': self.category.id,
                'status': 'planned',
                'return_year': '2025',
                'return_month': '6',
            },
            HTTP_HX_REQUEST='true'
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('HX-Redirect', response)
        self.assertNotIn('HX-Trigger', response)
        self.assertContains(response, 'Mai 2025')
        self.assertContains(response, 'Zur Monatsansicht')
        self.assertTrue(Booking.objects.filter(description='Other Month Receipt').exists())
