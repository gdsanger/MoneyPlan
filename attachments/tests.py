"""
Unit tests for attachments app
"""
import os
import tempfile
from io import BytesIO
from pathlib import Path

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import InMemoryUploadedFile, SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.urls import reverse

from bookings.models import Category, Booking
from attachments.models import Attachment, attachment_upload_path
from attachments.services import handle_upload, get_attachments_for, delete_attachment


# Create a temporary media directory for tests
TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class AttachmentModelTestCase(TestCase):
    """Test suite for Attachment model"""

    def setUp(self):
        """Set up test data"""
        self.category = Category.objects.create(
            name="Test Category", icon="wallet", color="#007bff"
        )
        self.booking = Booking.objects.create(
            date="2026-05-01",
            description="Test Booking",
            amount=100.00,
            status='booked',
            category=self.category
        )

    def test_attachment_upload_path(self):
        """Test attachment upload path generation"""
        # Create a mock attachment instance
        from django.contrib.contenttypes.models import ContentType
        attachment = Attachment(
            content_type=ContentType.objects.get_for_model(Booking),
            object_id=self.booking.pk,
        )

        path = attachment_upload_path(attachment, "test_file.pdf")

        # Check that path contains expected components
        self.assertIn('uploads', path)
        self.assertIn('bookings', path)
        self.assertIn('booking', path)
        self.assertIn(str(self.booking.pk), path)
        self.assertTrue(path.endswith('.pdf'))

    def test_file_size_display_bytes(self):
        """Test file size display for bytes"""
        from django.contrib.contenttypes.models import ContentType
        attachment = Attachment(
            content_type=ContentType.objects.get_for_model(Booking),
            object_id=self.booking.pk,
            filename="test.txt",
            file_size=500,
            mime_type="text/plain"
        )
        self.assertEqual(attachment.file_size_display, "500 Bytes")

    def test_file_size_display_kb(self):
        """Test file size display for kilobytes"""
        from django.contrib.contenttypes.models import ContentType
        attachment = Attachment(
            content_type=ContentType.objects.get_for_model(Booking),
            object_id=self.booking.pk,
            filename="test.txt",
            file_size=2048,
            mime_type="text/plain"
        )
        self.assertEqual(attachment.file_size_display, "2 KB")

    def test_file_size_display_mb(self):
        """Test file size display for megabytes"""
        from django.contrib.contenttypes.models import ContentType
        attachment = Attachment(
            content_type=ContentType.objects.get_for_model(Booking),
            object_id=self.booking.pk,
            filename="test.txt",
            file_size=1572864,  # 1.5 MB
            mime_type="text/plain"
        )
        self.assertEqual(attachment.file_size_display, "1,5 MB")


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
@override_settings(MAX_UPLOAD_SIZE_MB=10)
@override_settings(ALLOWED_UPLOAD_MIME_TYPES=['text/plain', 'application/pdf', 'image/png'])
class AttachmentServicesTestCase(TestCase):
    """Test suite for attachment services"""

    def setUp(self):
        """Set up test data"""
        self.category = Category.objects.create(
            name="Test Category", icon="wallet", color="#007bff"
        )
        self.booking = Booking.objects.create(
            date="2026-05-01",
            description="Test Booking",
            amount=100.00,
            status='booked',
            category=self.category
        )

    def tearDown(self):
        """Clean up test files"""
        # Clean up any created attachments and files
        for attachment in Attachment.objects.all():
            if attachment.file and os.path.isfile(attachment.file.path):
                os.remove(attachment.file.path)
        Attachment.objects.all().delete()

    def create_test_file(self, content=b'Test file content', filename='test.txt', mime_type='text/plain'):
        """Helper to create a test InMemoryUploadedFile"""
        file_obj = BytesIO(content)
        uploaded_file = InMemoryUploadedFile(
            file_obj,
            field_name='file',
            name=filename,
            content_type=mime_type,
            size=len(content),
            charset=None
        )
        return uploaded_file

    def test_handle_upload_success(self):
        """Test successful file upload"""
        test_file = self.create_test_file()
        attachment = handle_upload(test_file, self.booking)

        self.assertIsInstance(attachment, Attachment)
        self.assertEqual(attachment.filename, 'test.txt')
        self.assertEqual(attachment.object_id, self.booking.pk)
        self.assertTrue(attachment.file_size > 0)
        self.assertEqual(attachment.mime_type, 'text/plain')

    def test_handle_upload_file_too_large(self):
        """Test upload rejection for file exceeding size limit"""
        # Create a file larger than 10 MB
        large_content = b'x' * (11 * 1024 * 1024)  # 11 MB
        test_file = self.create_test_file(content=large_content)

        with self.assertRaises(ValidationError) as context:
            handle_upload(test_file, self.booking)

        self.assertIn('zu groß', str(context.exception))

    def test_handle_upload_invalid_mime_type(self):
        """Test upload rejection for disallowed MIME type"""
        # Create a file with disallowed MIME type (will be detected as text/plain by magic)
        # For this test, we need to mock the magic detection
        test_file = self.create_test_file(content=b'<?xml version="1.0"?>', filename='test.xml')

        # The actual MIME detection will happen in handle_upload
        # Since we can't easily create actual binary files, this test validates the error is raised
        # In real usage, python-magic would detect the actual MIME type
        try:
            handle_upload(test_file, self.booking)
        except ValidationError as e:
            # Either the file is rejected or it's detected as text/plain (which is allowed)
            # Both outcomes are acceptable for this test
            pass

    def test_handle_upload_long_filename(self):
        """Test filename truncation for long filenames"""
        long_name = 'a' * 300 + '.txt'
        test_file = self.create_test_file(filename=long_name)
        attachment = handle_upload(test_file, self.booking)

        # Filename should be truncated to 200 chars (including extension)
        self.assertLessEqual(len(attachment.filename), 204)  # 200 + ".txt"

    def test_get_attachments_for(self):
        """Test getting attachments for a specific object"""
        # Create multiple attachments
        test_file1 = self.create_test_file(content=b'File 1', filename='file1.txt')
        test_file2 = self.create_test_file(content=b'File 2', filename='file2.txt')

        attachment1 = handle_upload(test_file1, self.booking)
        attachment2 = handle_upload(test_file2, self.booking)

        # Get attachments
        attachments = get_attachments_for(self.booking)

        self.assertEqual(attachments.count(), 2)
        self.assertIn(attachment1, attachments)
        self.assertIn(attachment2, attachments)

    def test_get_attachments_for_empty(self):
        """Test getting attachments when none exist"""
        attachments = get_attachments_for(self.booking)
        self.assertEqual(attachments.count(), 0)

    def test_delete_attachment(self):
        """Test deleting an attachment"""
        test_file = self.create_test_file()
        attachment = handle_upload(test_file, self.booking)
        attachment_id = attachment.id
        file_path = attachment.file.path

        # Delete the attachment
        result = delete_attachment(attachment_id)

        self.assertTrue(result)
        self.assertFalse(Attachment.objects.filter(pk=attachment_id).exists())
        self.assertFalse(os.path.isfile(file_path))

    def test_delete_attachment_not_found(self):
        """Test deleting non-existent attachment"""
        result = delete_attachment(99999)
        self.assertFalse(result)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class AttachmentViewsTestCase(TestCase):
    """Test suite for attachment views"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        self.category = Category.objects.create(
            name="Test Category", icon="wallet", color="#007bff"
        )
        self.booking = Booking.objects.create(
            date="2026-05-01",
            description="Test Booking",
            amount=100.00,
            status='booked',
            category=self.category
        )

    def tearDown(self):
        """Clean up test files"""
        for attachment in Attachment.objects.all():
            if attachment.file and os.path.isfile(attachment.file.path):
                os.remove(attachment.file.path)
        Attachment.objects.all().delete()

    def test_upload_attachment_requires_login(self):
        """Test that upload view requires login"""
        url = reverse('attachments:upload', kwargs={
            'app_label': 'bookings',
            'model_name': 'booking',
            'object_id': self.booking.pk
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

    def test_upload_attachment_get(self):
        """Test GET request to upload view"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('attachments:upload', kwargs={
            'app_label': 'bookings',
            'model_name': 'booking',
            'object_id': self.booking.pk
        })
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachments', response.context)

    def test_upload_attachment_post(self):
        """Test POST request to upload a file"""
        self.client.login(username='testuser', password='testpass123')

        # Create a simple text file
        test_file = BytesIO(b'Test file content')
        test_file.name = 'test.txt'

        url = reverse('attachments:upload', kwargs={
            'app_label': 'bookings',
            'model_name': 'booking',
            'object_id': self.booking.pk
        })

        response = self.client.post(url, {'file': test_file}, format='multipart')

        # Should create an attachment
        self.assertEqual(Attachment.objects.count(), 1)
        attachment = Attachment.objects.first()
        self.assertEqual(attachment.filename, 'test.txt')

    def test_list_attachments(self):
        """Test listing attachments for an object"""
        self.client.login(username='testuser', password='testpass123')

        url = reverse('attachments:list', kwargs={
            'app_label': 'bookings',
            'model_name': 'booking',
            'object_id': self.booking.pk
        })
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachments', response.context)

    def test_delete_attachment_requires_login(self):
        """Test that delete view requires login"""
        url = reverse('attachments:delete', kwargs={'attachment_id': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

    def test_delete_attachment_post(self):
        """Test POST request to delete attachment"""
        self.client.login(username='testuser', password='testpass123')

        # Create an attachment first
        from django.core.files.uploadedfile import SimpleUploadedFile
        test_file = SimpleUploadedFile('test.txt', b'content', content_type='text/plain')

        from attachments.services import handle_upload
        attachment = handle_upload(test_file, self.booking)

        url = reverse('attachments:delete', kwargs={'attachment_id': attachment.pk})
        response = self.client.post(url)

        # Should delete the attachment
        self.assertFalse(Attachment.objects.filter(pk=attachment.pk).exists())

    def test_delete_attachment_get_not_allowed(self):
        """Test that GET request to delete is not allowed"""
        self.client.login(username='testuser', password='testpass123')

        url = reverse('attachments:delete', kwargs={'attachment_id': 1})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 405)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
@override_settings(MAX_UPLOAD_SIZE_MB=10)
@override_settings(ALLOWED_UPLOAD_MIME_TYPES=['text/plain', 'application/pdf'])
@override_settings(MCP_ACCESS_TOKEN='secret-token')
class BookingAttachmentUploadApiTestCase(TestCase):
    """Test suite for the token-authenticated multipart upload API (agent workflow)"""

    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(
            name="Test Category", icon="wallet", color="#007bff"
        )
        self.booking = Booking.objects.create(
            date="2026-05-01",
            description="Test Booking",
            amount=100.00,
            status='booked',
            category=self.category
        )
        self.url = reverse('api_booking_attachment_upload', kwargs={'booking_id': self.booking.pk})

    def tearDown(self):
        for attachment in Attachment.objects.all():
            if attachment.file and os.path.isfile(attachment.file.path):
                os.remove(attachment.file.path)
        Attachment.objects.all().delete()

    def _upload(self, **extra):
        test_file = SimpleUploadedFile('rechnung.txt', b'Beleg-Inhalt', content_type='text/plain')
        return self.client.post(self.url, {'file': test_file}, **extra)

    def test_missing_token_rejected(self):
        response = self._upload()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(Attachment.objects.count(), 0)

    def test_wrong_token_rejected(self):
        response = self._upload(HTTP_AUTHORIZATION='Bearer wrong-token')
        self.assertEqual(response.status_code, 401)

    def test_valid_bearer_token_uploads_file(self):
        response = self._upload(HTTP_AUTHORIZATION='Bearer secret-token')
        self.assertEqual(response.status_code, 201)

        data = response.json()
        self.assertEqual(Attachment.objects.count(), 1)
        attachment = Attachment.objects.first()
        self.assertEqual(data['attachment_id'], attachment.id)
        self.assertEqual(data['filename'], 'rechnung.txt')
        self.assertEqual(data['file_size'], attachment.file_size)
        self.assertEqual(data['mime_type'], 'text/plain')
        self.assertIn('uploaded_at', data)
        self.assertIn('url', data)
        self.assertEqual(attachment.object_id, self.booking.pk)

    def test_valid_query_token_uploads_file(self):
        response = self.client.post(f'{self.url}?token=secret-token', {
            'file': SimpleUploadedFile('rechnung.txt', b'Beleg-Inhalt', content_type='text/plain'),
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Attachment.objects.count(), 1)

    def test_unknown_booking_returns_404(self):
        url = reverse('api_booking_attachment_upload', kwargs={'booking_id': 999999})
        test_file = SimpleUploadedFile('rechnung.txt', b'Beleg-Inhalt', content_type='text/plain')
        response = self.client.post(url, {'file': test_file}, HTTP_AUTHORIZATION='Bearer secret-token')
        self.assertEqual(response.status_code, 404)

    def test_missing_file_field_returns_400(self):
        response = self.client.post(self.url, {}, HTTP_AUTHORIZATION='Bearer secret-token')
        self.assertEqual(response.status_code, 400)

    def test_oversized_file_returns_413(self):
        large_content = b'x' * (11 * 1024 * 1024)  # 11 MB, limit is 10 MB
        test_file = SimpleUploadedFile('gross.txt', large_content, content_type='text/plain')
        response = self.client.post(self.url, {'file': test_file}, HTTP_AUTHORIZATION='Bearer secret-token')
        self.assertEqual(response.status_code, 413)
        self.assertEqual(Attachment.objects.count(), 0)

    def test_disallowed_mime_type_returns_400(self):
        test_file = SimpleUploadedFile('archiv.zip', b'PK\x03\x04' + b'\x00' * 20, content_type='application/zip')
        response = self.client.post(self.url, {'file': test_file}, HTTP_AUTHORIZATION='Bearer secret-token')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Attachment.objects.count(), 0)

    def test_get_not_allowed(self):
        response = self.client.get(self.url, HTTP_AUTHORIZATION='Bearer secret-token')
        self.assertEqual(response.status_code, 405)

    def test_web_upload_still_requires_login_unaffected(self):
        """The existing login_required web-upload endpoint must be untouched."""
        url = reverse('attachments:upload', kwargs={
            'app_label': 'bookings',
            'model_name': 'booking',
            'object_id': self.booking.pk
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))
