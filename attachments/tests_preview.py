from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
import tempfile
from datetime import date

from bookings.models import Booking, Category
from attachments.models import Attachment
from django.contrib.contenttypes.models import ContentType


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AttachmentPreviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('u', password='p')
        self.client.force_login(self.user)
        self.booking = Booking.objects.create(category=Category.objects.create(name='K'), date=date.today(), description='Test', amount=-10)
        self.att = Attachment.objects.create(
            content_type=ContentType.objects.get_for_model(Booking), object_id=self.booking.pk,
            file=SimpleUploadedFile('a.pdf', b'%PDF-1.4 test'), filename='a.pdf',
            file_size=13, mime_type='application/pdf')

    def test_file_served_inline_and_frameable(self):
        r = self.client.get(reverse('attachments:file', args=[self.att.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertEqual(r['X-Frame-Options'], 'SAMEORIGIN')

    def test_preview_modal_content(self):
        r = self.client.get(reverse('attachments:preview', args=['bookings', 'booking', self.booking.pk]))
        self.assertContains(r, reverse('attachments:file', args=[self.att.pk]))

    def test_edit_page_embeds_preview(self):
        r = self.client.get(reverse('bookings:edit', args=[self.booking.pk]))
        self.assertContains(r, '<iframe')
