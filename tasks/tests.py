"""
Unit tests for tasks app
"""
from datetime import date, timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from tasks.models import Task


class TaskModelTestCase(TestCase):
    """Test suite for Task model"""

    def setUp(self):
        """Set up test data"""
        self.today = date.today()

    def test_task_creation(self):
        """Test basic task creation"""
        task = Task.objects.create(
            title="Test Task",
            description="Test description",
            due_date=self.today,
            priority="high",
            status="open"
        )
        self.assertEqual(task.title, "Test Task")
        self.assertEqual(task.priority, "high")
        self.assertEqual(task.status, "open")
        self.assertEqual(str(task), "Test Task")

    def test_is_overdue_property(self):
        """Test is_overdue property"""
        # Overdue task
        overdue_task = Task.objects.create(
            title="Overdue Task",
            due_date=self.today - timedelta(days=1),
            status="open"
        )
        self.assertTrue(overdue_task.is_overdue)

        # Not overdue task
        future_task = Task.objects.create(
            title="Future Task",
            due_date=self.today + timedelta(days=1),
            status="open"
        )
        self.assertFalse(future_task.is_overdue)

        # Done task (not overdue even if past due date)
        done_task = Task.objects.create(
            title="Done Task",
            due_date=self.today - timedelta(days=1),
            status="done"
        )
        self.assertFalse(done_task.is_overdue)

    def test_is_due_soon_property(self):
        """Test is_due_soon property"""
        # Due today
        due_today = Task.objects.create(
            title="Due Today",
            due_date=self.today,
            status="open"
        )
        self.assertTrue(due_today.is_due_soon)

        # Due in 2 days
        due_soon = Task.objects.create(
            title="Due Soon",
            due_date=self.today + timedelta(days=2),
            status="open"
        )
        self.assertTrue(due_soon.is_due_soon)

        # Due in 4 days (not soon)
        not_due_soon = Task.objects.create(
            title="Not Due Soon",
            due_date=self.today + timedelta(days=4),
            status="open"
        )
        self.assertFalse(not_due_soon.is_due_soon)

        # Done task
        done_task = Task.objects.create(
            title="Done Task",
            due_date=self.today,
            status="done"
        )
        self.assertFalse(done_task.is_due_soon)

    def test_task_ordering(self):
        """Test default ordering by due_date and title"""
        Task.objects.create(title="Task A", due_date=self.today + timedelta(days=2), priority="low")
        Task.objects.create(title="Task B", due_date=self.today + timedelta(days=1), priority="high")
        Task.objects.create(title="Task C", due_date=self.today + timedelta(days=1), priority="low")

        tasks = list(Task.objects.all())
        # Should be ordered by due_date, then title
        self.assertEqual(tasks[0].title, "Task B")  # day 1, comes first alphabetically
        self.assertEqual(tasks[1].title, "Task C")  # day 1, comes second alphabetically
        self.assertEqual(tasks[2].title, "Task A")  # day 2


class TaskViewsTestCase(TestCase):
    """Test suite for task views"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')
        self.today = date.today()

    def test_task_list_view(self):
        """Test task list view"""
        Task.objects.create(title="Task 1", status="open")
        Task.objects.create(title="Task 2", status="done")

        response = self.client.get(reverse('tasks:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Task 1")
        self.assertContains(response, "Task 2")

    def test_task_list_filter_by_status(self):
        """Test task list filtering by status"""
        Task.objects.create(title="Open Task", status="open")
        Task.objects.create(title="Done Task", status="done")

        response = self.client.get(reverse('tasks:list') + '?status=open')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open Task")
        self.assertNotContains(response, "Done Task")

    def test_task_list_filter_by_priority(self):
        """Test task list filtering by priority"""
        Task.objects.create(title="High Priority", priority="high")
        Task.objects.create(title="Low Priority", priority="low")

        response = self.client.get(reverse('tasks:list') + '?priority=high')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "High Priority")
        self.assertNotContains(response, "Low Priority")

    def test_task_create_view_get(self):
        """Test task create view GET request"""
        response = self.client.get(reverse('tasks:create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Neue Aufgabe")

    def test_task_create_view_post(self):
        """Test task create view POST request"""
        data = {
            'title': 'New Task',
            'description': 'Test description',
            'due_date': self.today,
            'priority': 'medium',
            'status': 'open'
        }
        response = self.client.post(reverse('tasks:create'), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        self.assertTrue(Task.objects.filter(title='New Task').exists())

    def test_task_edit_view_get(self):
        """Test task edit view GET request"""
        task = Task.objects.create(title="Edit Me", status="open")
        response = self.client.get(reverse('tasks:edit', args=[task.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit Me")

    def test_task_edit_view_post(self):
        """Test task edit view POST request"""
        task = Task.objects.create(title="Old Title", status="open")
        data = {
            'title': 'Updated Title',
            'description': 'Updated description',
            'priority': 'high',
            'status': 'open'
        }
        response = self.client.post(reverse('tasks:edit', args=[task.id]), data)
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.title, 'Updated Title')

    def test_task_delete_view(self):
        """Test task delete view"""
        task = Task.objects.create(title="Delete Me", status="open")
        response = self.client.post(reverse('tasks:delete', args=[task.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Task.objects.filter(id=task.id).exists())

    def test_task_toggle_done_view(self):
        """Test task toggle done view"""
        task = Task.objects.create(title="Toggle Me", status="open")
        response = self.client.post(reverse('tasks:toggle_done', args=[task.id]))
        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, 'done')

        # Toggle back
        response = self.client.post(reverse('tasks:toggle_done', args=[task.id]))
        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, 'open')

    def test_task_views_require_login(self):
        """Test that task views require authentication"""
        self.client.logout()

        response = self.client.get(reverse('tasks:list'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

        response = self.client.get(reverse('tasks:create'))
        self.assertEqual(response.status_code, 302)

