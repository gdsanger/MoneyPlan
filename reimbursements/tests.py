"""Tests for reimbursements app."""
from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse

from bookings.services import get_forecast
from reimbursements.models import ExpenseClaim, ReimbursementConfig, ReimbursementSubmission
from reimbursements.receipt_service import FuelReceiptResult
from reimbursements.services import get_forecast_entry, get_unreimbursed_total


class ReimbursementServicesTestCase(TestCase):
    def setUp(self):
        ExpenseClaim.objects.create(
            date=date(2026, 4, 27),
            description='Shell',
            amount=Decimal('101.07'),
            status=ExpenseClaim.STATUS_PENDING,
        )
        ExpenseClaim.objects.create(
            date=date(2026, 4, 29),
            description='Aral',
            amount=Decimal('64.87'),
            status=ExpenseClaim.STATUS_SUBMITTED,
        )
        ExpenseClaim.objects.create(
            date=date(2026, 3, 1),
            description='Alt',
            amount=Decimal('50.00'),
            status=ExpenseClaim.STATUS_REIMBURSED,
        )

    def test_get_unreimbursed_total(self):
        self.assertEqual(get_unreimbursed_total(), Decimal('165.94'))

    def test_get_forecast_entry(self):
        entry = get_forecast_entry()
        self.assertIsNotNone(entry)
        self.assertEqual(entry['date'].day, 15)
        self.assertEqual(entry['amount'], Decimal('165.94'))
        self.assertEqual(entry['source'], 'reimbursements')

    def test_forecast_merge_with_reimbursements(self):
        forecast = get_forecast(months=6)
        months_with_reimbursements = [
            item for item in forecast if 'reimbursements_amount' in item
        ]
        self.assertEqual(len(months_with_reimbursements), 1)
        self.assertEqual(
            months_with_reimbursements[0]['reimbursements_amount'],
            Decimal('165.94'),
        )


class ReimbursementViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')
        self.config = ReimbursementConfig.get()
        self.config.employee_name = 'Christian Angermeier'
        self.config.recipient_email = 'hr@isartec.example'
        self.config.save()

    def test_claim_list_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('reimbursements:list'))
        self.assertEqual(response.status_code, 302)

    def test_claim_list_get(self):
        response = self.client.get(reverse('reimbursements:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Auslagen ISARtec')

    @patch('reimbursements.views.magic.from_buffer')
    @patch('reimbursements.views.recognize_fuel_receipt')
    def test_receipt_upload_post_success(self, mock_recognize, mock_magic):
        mock_magic.return_value = 'image/jpeg'
        mock_recognize.return_value = FuelReceiptResult(
            date='2026-04-27',
            description='Shell Landshut',
            amount=Decimal('101.07'),
            notes='Diesel',
            confidence={'date': 'high', 'amount': 'high', 'description': 'high'},
            raw_text='Shell 101.07 EUR',
            ai_provider='openai',
            ai_model='gpt-4o',
        )
        image_file = SimpleUploadedFile('receipt.jpg', b'fake image', content_type='image/jpeg')
        response = self.client.post(
            reverse('reimbursements:receipt_upload'),
            {'receipt_file': image_file},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tankbeleg erkannt')
        self.assertIn('fuel_receipt_result', self.client.session)

    @patch('reimbursements.views.handle_upload')
    @patch('reimbursements.views.magic.from_buffer')
    @patch('reimbursements.views.recognize_fuel_receipt')
    def test_receipt_confirm_creates_claim(self, mock_recognize, mock_magic, mock_upload):
        mock_magic.return_value = 'image/jpeg'
        mock_recognize.return_value = FuelReceiptResult(
            date='2026-04-27',
            description='Shell Landshut',
            amount=Decimal('101.07'),
            notes='',
            confidence={'date': 'high', 'amount': 'high', 'description': 'high'},
            raw_text='Shell',
            ai_provider='openai',
            ai_model='gpt-4o',
        )
        image_file = SimpleUploadedFile('receipt.jpg', b'fake image', content_type='image/jpeg')
        self.client.post(
            reverse('reimbursements:receipt_upload'),
            {'receipt_file': image_file},
            HTTP_HX_REQUEST='true',
        )
        mock_upload.return_value = MagicMock()
        response = self.client.post(
            reverse('reimbursements:receipt_confirm'),
            {
                'date': '2026-04-27',
                'description': 'Shell Landshut',
                'amount': '101.07',
                'notes': '',
            },
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 204)
        claim = ExpenseClaim.objects.get(description='Shell Landshut')
        self.assertEqual(claim.status, ExpenseClaim.STATUS_PENDING)
        self.assertEqual(claim.amount, Decimal('101.07'))

    @patch('reimbursements.views.handle_upload')
    @patch('reimbursements.views.magic.from_buffer')
    @patch('reimbursements.views.recognize_fuel_receipt')
    def test_receipt_confirm_upload_failure_no_duplicate(self, mock_recognize, mock_magic, mock_upload):
        mock_magic.return_value = 'image/jpeg'
        mock_recognize.return_value = FuelReceiptResult(
            date='2026-04-27',
            description='Shell Landshut',
            amount=Decimal('101.07'),
            notes='',
            confidence={'date': 'high', 'amount': 'high', 'description': 'high'},
            raw_text='Shell',
            ai_provider='openai',
            ai_model='gpt-4o',
        )
        mock_upload.side_effect = ValidationError('Datei zu groß')

        image_file = SimpleUploadedFile('receipt.jpg', b'fake image', content_type='image/jpeg')
        self.client.post(
            reverse('reimbursements:receipt_upload'),
            {'receipt_file': image_file},
            HTTP_HX_REQUEST='true',
        )

        confirm_data = {
            'date': '2026-04-27',
            'description': 'Shell Landshut',
            'amount': '101.07',
            'notes': '',
        }
        response = self.client.post(
            reverse('reimbursements:receipt_confirm'),
            confirm_data,
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Datei zu groß')
        self.assertEqual(ExpenseClaim.objects.count(), 0)
        self.assertIn('fuel_receipt_result', self.client.session)

        response = self.client.post(
            reverse('reimbursements:receipt_confirm'),
            confirm_data,
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(ExpenseClaim.objects.count(), 0)
        self.assertIn('fuel_receipt_result', self.client.session)

    @patch('reimbursements.views.send_submission_mail')
    @patch('reimbursements.views.generate_submission_pdf')
    def test_submit_claims(self, mock_pdf, mock_mail):
        claim = ExpenseClaim.objects.create(
            date=date(2026, 4, 27),
            description='Shell',
            amount=Decimal('101.07'),
            status=ExpenseClaim.STATUS_PENDING,
        )
        mock_pdf.return_value = (b'%PDF-1.4 fake', '20260427 ISARtec Auslagenerstattung.pdf')
        mock_mail.return_value = (True, 'OK')

        response = self.client.post(reverse('reimbursements:submit'))
        self.assertEqual(response.status_code, 302)
        claim.refresh_from_db()
        self.assertEqual(claim.status, ExpenseClaim.STATUS_SUBMITTED)
        self.assertIsNotNone(claim.submitted_at)
        self.assertEqual(ReimbursementSubmission.objects.count(), 1)
        mock_mail.assert_called_once()

    def test_settings_save(self):
        response = self.client.post(reverse('reimbursements:settings'), {
            'employee_name': 'Test User',
            'bank_name': 'Testbank',
            'iban': 'DE00123456789012345678',
            'bic': 'TESTDEFFXXX',
            'expense_purpose': 'Tanken Test',
            'place': 'München',
            'recipient_email': 'test@example.com',
        })
        self.assertEqual(response.status_code, 302)
        config = ReimbursementConfig.get()
        self.assertEqual(config.employee_name, 'Test User')
        self.assertEqual(config.recipient_email, 'test@example.com')


class PdfServiceTestCase(TestCase):
    @patch('reimbursements.pdf_service._append_attachment_pages')
    @patch('reimbursements.pdf_service.generate_application_pdf_bytes')
    def test_generate_submission_pdf(self, mock_app_pdf, mock_append):
        from pypdf import PdfWriter
        from reimbursements.pdf_service import generate_submission_pdf

        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        buffer = BytesIO()
        writer.write(buffer)
        mock_app_pdf.return_value = buffer.getvalue()

        ReimbursementConfig.get()
        claim = ExpenseClaim.objects.create(
            date=date(2026, 4, 27),
            description='Shell',
            amount=Decimal('101.07'),
            status=ExpenseClaim.STATUS_PENDING,
        )

        pdf_bytes, filename = generate_submission_pdf([claim])

        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        self.assertIn('ISARtec Auslagenerstattung.pdf', filename)
        mock_app_pdf.assert_called_once()
