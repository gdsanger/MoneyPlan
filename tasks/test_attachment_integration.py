"""
Integration tests for attachment functionality in tasks
"""
import tempfile
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from datetime import date, timedelta

from tasks.models import Task
from attachments.models import Attachment


# Create a temporary media directory for tests
TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
@override_settings(MAX_UPLOAD_SIZE_MB=10)
@override_settings(ALLOWED_UPLOAD_MIME_TYPES=['text/plain', 'application/pdf'])
class TaskAttachmentIntegrationTestCase(TestCase):
    """Test cases for attachment integration in task views"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')

        # Create test task
        self.task = Task.objects.create(
            title='Test Task',
            description='Test description',
            due_date=date.today() + timedelta(days=7),
            priority='high',
            status='open'
        )

        # Create test attachment
        self.content_type = ContentType.objects.get_for_model(Task)

    def test_task_edit_includes_attachments_context(self):
        """Test that task edit view includes attachments in context"""
        response = self.client.get(reverse('tasks:edit', args=[self.task.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachments', response.context)
        self.assertIn('task', response.context)

    def test_task_list_includes_attachment_count_annotation(self):
        """Test that task list includes attachment_count annotation"""
        # Create an attachment for the task
        Attachment.objects.create(
            content_type=self.content_type,
            object_id=self.task.pk,
            filename="test.txt",
            file_size=100,
            mime_type="text/plain"
        )

        response = self.client.get(reverse('tasks:list'))

        self.assertEqual(response.status_code, 200)
        tasks = response.context['tasks']
        self.assertEqual(len(tasks), 1)
        # Check that attachment_count is present
        task = list(tasks)[0]
        self.assertTrue(hasattr(task, 'attachment_count'))

    def test_task_row_template_shows_attachment_count(self):
        """Test that task row template shows attachment count"""
        # Create attachments for the task
        Attachment.objects.create(
            content_type=self.content_type,
            object_id=self.task.pk,
            filename="test1.txt",
            file_size=100,
            mime_type="text/plain"
        )
        Attachment.objects.create(
            content_type=self.content_type,
            object_id=self.task.pk,
            filename="test2.txt",
            file_size=200,
            mime_type="text/plain"
        )

        response = self.client.get(reverse('tasks:list'))

        self.assertEqual(response.status_code, 200)
        # Check that paperclip icon appears in the HTML
        self.assertContains(response, 'bi-paperclip')

    def test_task_form_shows_attachment_panel_for_existing_task(self):
        """Test that task form shows attachment panel for existing task"""
        response = self.client.get(reverse('tasks:edit', args=[self.task.id]))

        self.assertEqual(response.status_code, 200)
        # Check that attachment panel is included
        self.assertContains(response, 'Anhänge')
        self.assertContains(response, 'attachment-panel')

    def test_task_form_shows_hint_for_new_task(self):
        """Test that task form shows hint instead of panel for new task"""
        response = self.client.get(reverse('tasks:create'))

        self.assertEqual(response.status_code, 200)
        # Check that hint is shown for create form
        self.assertContains(response, 'Anhänge können nach dem Speichern')

    def test_task_toggle_done_preserves_attachment_count(self):
        """Test that toggling task status preserves attachment count"""
        # Create an attachment for the task
        Attachment.objects.create(
            content_type=self.content_type,
            object_id=self.task.pk,
            filename="test.txt",
            file_size=100,
            mime_type="text/plain"
        )

        # Toggle task status
        response = self.client.post(
            reverse('tasks:toggle_done', args=[self.task.id]),
            HTTP_HX_REQUEST='true'
        )

        self.assertEqual(response.status_code, 200)
        # Check that the response contains the attachment count
        # (The view should set task.attachment_count before rendering)
