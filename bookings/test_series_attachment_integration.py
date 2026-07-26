"""
Integration tests for attachment functionality on recurring series
"""
import tempfile
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal
from datetime import date

from bookings.models import RecurringSeries, Category
from attachments.models import Attachment


TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
@override_settings(MAX_UPLOAD_SIZE_MB=10)
@override_settings(ALLOWED_UPLOAD_MIME_TYPES=['text/plain', 'application/pdf'])
class SeriesAttachmentIntegrationTestCase(TestCase):
    """Test cases for attachment integration on recurring series"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')

        self.category = Category.objects.create(
            name='Test Kategorie',
            icon='wallet',
            color='#007bff'
        )

        self.series = RecurringSeries.objects.create(
            description='Mietvertrag',
            amount=Decimal('-1000.00'),
            interval='monthly',
            start_date=date(2025, 1, 1),
            category=self.category,
        )

        self.content_type = ContentType.objects.get_for_model(RecurringSeries)

    def test_series_list_includes_attachment_count_annotation(self):
        Attachment.objects.create(
            content_type=self.content_type,
            object_id=self.series.pk,
            filename="vertrag.pdf",
            file_size=100,
            mime_type="application/pdf",
        )

        response = self.client.get(reverse('bookings:series_list'))

        self.assertEqual(response.status_code, 200)
        item = next(
            i for i in response.context['series_with_counts']
            if i['series'].pk == self.series.pk
        )
        self.assertEqual(item['attachment_count'], 1)
        self.assertContains(response, 'bi-paperclip')

    def test_generic_attachment_list_view_works_for_series(self):
        response = self.client.get(reverse(
            'attachments:list', args=['bookings', 'recurringseries', self.series.id]
        ))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['object'], self.series)

    def test_generic_attachment_upload_view_works_for_series(self):
        upload = tempfile.NamedTemporaryFile(suffix='.txt')
        upload.write(b'Vertragsinhalt')
        upload.seek(0)

        response = self.client.post(
            reverse('attachments:upload', args=['bookings', 'recurringseries', self.series.id]),
            {'file': upload},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Attachment.objects.filter(content_type=self.content_type, object_id=self.series.pk).exists()
        )

    def test_series_attachment_is_deleted_independently_of_bookings(self):
        attachment = Attachment.objects.create(
            content_type=self.content_type,
            object_id=self.series.pk,
            filename="vertrag.pdf",
            file_size=100,
            mime_type="application/pdf",
        )

        response = self.client.post(reverse('attachments:delete', args=[attachment.id]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Attachment.objects.filter(pk=attachment.pk).exists())
        # The series itself must remain untouched
        self.assertTrue(RecurringSeries.objects.filter(pk=self.series.pk).exists())
