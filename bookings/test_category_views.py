from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date
from bookings.models import Booking, Category
from bookings.forms import CategoryForm


class CategoryViewsTestCase(TestCase):
    """Test cases for category views"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        # Create test categories
        self.category1 = Category.objects.create(
            name='Test Kategorie 1',
            icon='wallet',
            color='#007bff'
        )

        self.category2 = Category.objects.create(
            name='Test Kategorie 2',
            icon='house',
            color='#28a745'
        )

    def test_category_list_requires_login(self):
        """Test that category list requires login"""
        response = self.client.get(reverse('category_list'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

    def test_category_list_view(self):
        """Test category list view displays categories"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('category_list'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/category_list.html')
        self.assertIn('categories', response.context)
        self.assertEqual(len(response.context['categories']), 2)

    def test_category_list_shows_booking_count(self):
        """Test category list shows booking count"""
        # Create a booking for category1
        Booking.objects.create(
            date=date(2025, 1, 15),
            description='Test Booking',
            amount=Decimal('100.00'),
            status='planned',
            category=self.category1
        )

        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('category_list'))

        categories = response.context['categories']
        cat1 = next(c for c in categories if c.id == self.category1.id)
        cat2 = next(c for c in categories if c.id == self.category2.id)

        self.assertEqual(cat1.booking_count, 1)
        self.assertEqual(cat2.booking_count, 0)

    def test_category_create_get(self):
        """Test GET request to create category"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('category_create'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIsInstance(response.context['form'], CategoryForm)

    def test_category_create_post_valid(self):
        """Test POST request to create category with valid data"""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': 'Neue Kategorie',
            'icon': 'cart',
            'color': '#ff5733'
        }
        response = self.client.post(reverse('category_create'), data)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Category.objects.filter(name='Neue Kategorie').exists())

        new_category = Category.objects.get(name='Neue Kategorie')
        self.assertEqual(new_category.icon, 'bi-cart')  # Should have bi- prefix
        self.assertEqual(new_category.color, '#ff5733')

    def test_category_create_post_invalid(self):
        """Test POST request to create category with invalid data"""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': '',  # Empty name
            'icon': 'cart',
            'color': '#ff5733'
        }
        response = self.client.post(reverse('category_create'), data)

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'name', 'Dieses Feld ist zwingend erforderlich.')

    def test_category_create_duplicate_name(self):
        """Test creating category with duplicate name"""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': 'Test Kategorie 1',  # Already exists
            'icon': 'cart',
            'color': '#ff5733'
        }
        response = self.client.post(reverse('category_create'), data)

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'],
            'name',
            'Kategorie mit diesem Name existiert bereits.'
        )

    def test_category_edit_get(self):
        """Test GET request to edit category"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('category_edit', args=[self.category1.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIn('category', response.context)
        self.assertEqual(response.context['category'].id, self.category1.id)

    def test_category_edit_post_valid(self):
        """Test POST request to edit category with valid data"""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': 'Updated Category',
            'icon': 'star',
            'color': '#00ff00'
        }
        response = self.client.post(
            reverse('category_edit', args=[self.category1.id]),
            data
        )

        self.assertEqual(response.status_code, 302)
        self.category1.refresh_from_db()
        self.assertEqual(self.category1.name, 'Updated Category')
        self.assertEqual(self.category1.icon, 'bi-star')  # Should have bi- prefix
        self.assertEqual(self.category1.color, '#00ff00')

    def test_category_delete_no_bookings(self):
        """Test deleting category with no bookings"""
        self.client.login(username='testuser', password='testpass123')
        category_id = self.category1.id

        response = self.client.post(reverse('category_delete', args=[category_id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Category.objects.filter(id=category_id).exists())

    def test_category_delete_with_bookings(self):
        """Test deleting category with bookings (should fail)"""
        # Create a booking for category1
        Booking.objects.create(
            date=date(2025, 1, 15),
            description='Test Booking',
            amount=Decimal('100.00'),
            status='planned',
            category=self.category1
        )

        self.client.login(username='testuser', password='testpass123')
        category_id = self.category1.id

        response = self.client.post(reverse('category_delete', args=[category_id]))

        # Category should still exist
        self.assertTrue(Category.objects.filter(id=category_id).exists())
        # Should redirect back
        self.assertEqual(response.status_code, 302)

    def test_category_delete_with_bookings_htmx(self):
        """Test deleting category with bookings via HTMX (should return error)"""
        # Create a booking for category1
        Booking.objects.create(
            date=date(2025, 1, 15),
            description='Test Booking',
            amount=Decimal('100.00'),
            status='planned',
            category=self.category1
        )

        self.client.login(username='testuser', password='testpass123')
        category_id = self.category1.id

        response = self.client.post(
            reverse('category_delete', args=[category_id]),
            HTTP_HX_REQUEST='true'
        )

        # Should return 400 with error message
        self.assertEqual(response.status_code, 400)
        self.assertIn('Kategorie kann nicht gelöscht werden', response.content.decode())
        # Category should still exist
        self.assertTrue(Category.objects.filter(id=category_id).exists())

    def test_category_delete_get_not_allowed(self):
        """Test GET request to delete category is not allowed"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('category_delete', args=[self.category1.id]))

        self.assertEqual(response.status_code, 405)


class CategoryFormTestCase(TestCase):
    """Test cases for CategoryForm"""

    def test_form_valid_data(self):
        """Test form with valid data"""
        form = CategoryForm(data={
            'name': 'Test Category',
            'icon': 'wallet',
            'color': '#007bff'
        })
        self.assertTrue(form.is_valid())

    def test_form_missing_required_name(self):
        """Test form with missing required name"""
        form = CategoryForm(data={
            'icon': 'wallet',
            'color': '#007bff'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_form_missing_required_color(self):
        """Test form with missing required color"""
        form = CategoryForm(data={
            'name': 'Test Category',
            'icon': 'wallet'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('color', form.errors)

    def test_form_icon_optional(self):
        """Test form with no icon (should be valid)"""
        form = CategoryForm(data={
            'name': 'Test Category',
            'color': '#007bff'
        })
        self.assertTrue(form.is_valid())
