"""
Integration tests for attachment functionality in bookings
"""
import tempfile
from io import BytesIO
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal
from datetime import date

from bookings.models import Booking, Category
from attachments.models import Attachment


# Create a temporary media directory for tests
TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
@override_settings(MAX_UPLOAD_SIZE_MB=10)
@override_settings(ALLOWED_UPLOAD_MIME_TYPES=['text/plain', 'application/pdf'])
class BookingAttachmentIntegrationTestCase(TestCase):
    """Test cases for attachment integration in booking views"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')

        # Create test category
        self.category = Category.objects.create(
            name='Test Kategorie',
            icon='wallet',
            color='#007bff'
        )

        # Create test booking
        self.booking = Booking.objects.create(
            date=date(2025, 1, 15),
            description='Test Booking',
            amount=Decimal('1000.00'),
            status='planned',
            category=self.category
        )

        # Create test attachment
        self.content_type = ContentType.objects.get_for_model(Booking)

    def test_booking_edit_includes_attachments_context(self):
        """Test that booking edit view includes attachments in context"""
        response = self.client.get(reverse('bookings:edit', args=[self.booking.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachments', response.context)
        self.assertIn('booking', response.context)

    def test_booking_list_includes_attachment_count_annotation(self):
        """Test that booking list includes attachment_count annotation"""
        # Create an attachment for the booking
        Attachment.objects.create(
            content_type=self.content_type,
            object_id=self.booking.pk,
            filename="test.txt",
            file_size=100,
            mime_type="text/plain"
        )

        response = self.client.get(reverse('bookings:list'))

        self.assertEqual(response.status_code, 200)
        bookings = list(response.context['page_obj'])
        self.assertEqual(len(bookings), 1)
        # Check that attachment_count is present (may be None or 1)
        self.assertTrue(hasattr(bookings[0], 'attachment_count'))

    def test_booking_row_template_shows_attachment_count(self):
        """Test that booking row template shows attachment count"""
        # Create attachments for the booking
        Attachment.objects.create(
            content_type=self.content_type,
            object_id=self.booking.pk,
            filename="test1.txt",
            file_size=100,
            mime_type="text/plain"
        )
        Attachment.objects.create(
            content_type=self.content_type,
            object_id=self.booking.pk,
            filename="test2.txt",
            file_size=200,
            mime_type="text/plain"
        )

        response = self.client.get(reverse('bookings:list'))

        self.assertEqual(response.status_code, 200)
        # Check that paperclip icon appears in the HTML
        self.assertContains(response, 'bi-paperclip')

    def test_month_view_includes_attachment_count_annotation(self):
        """Test that month view includes attachment_count annotation"""
        # Create an attachment for the booking
        Attachment.objects.create(
            content_type=self.content_type,
            object_id=self.booking.pk,
            filename="test.txt",
            file_size=100,
            mime_type="text/plain"
        )

        response = self.client.get(reverse('bookings:month_view_detail', args=[2025, 1]))

        self.assertEqual(response.status_code, 200)
        # Check that bookings_with_balance contains bookings with attachment_count
        bookings_with_balance = response.context['bookings_with_balance']
        self.assertEqual(len(bookings_with_balance), 1)
        booking = bookings_with_balance[0]['booking']
        self.assertTrue(hasattr(booking, 'attachment_count'))

    def test_booking_form_shows_attachment_panel_for_existing_booking(self):
        """Test that booking form shows attachment panel for existing booking"""
        response = self.client.get(reverse('bookings:edit', args=[self.booking.id]))

        self.assertEqual(response.status_code, 200)
        # Check that attachment panel is included
        self.assertContains(response, 'Anhänge')
        self.assertContains(response, 'attachment-panel')

    def test_booking_form_shows_hint_for_new_booking(self):
        """Test that booking form shows hint instead of panel for new booking"""
        response = self.client.get(reverse('bookings:create'))

        self.assertEqual(response.status_code, 200)
        # Check that hint is shown for create form
        self.assertContains(response, 'Anhänge können nach dem Speichern')
