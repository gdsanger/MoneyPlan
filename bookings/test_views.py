from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date
from bookings.models import Booking, Category, RecurringSeries
from bookings.forms import BookingForm, BookingFilterForm


class BookingViewsTestCase(TestCase):
    """Test cases for booking views"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        # Create test category
        self.category = Category.objects.create(
            name='Test Kategorie',
            icon='wallet',
            color='#007bff'
        )

        # Create test bookings
        self.booking1 = Booking.objects.create(
            date=date(2025, 1, 15),
            description='Test Einnahme',
            amount=Decimal('1000.00'),
            status='planned',
            category=self.category
        )

        self.booking2 = Booking.objects.create(
            date=date(2025, 1, 20),
            description='Test Ausgabe',
            amount=Decimal('-500.00'),
            status='booked',
            category=self.category
        )

    def test_booking_list_requires_login(self):
        """Test that booking list requires login"""
        response = self.client.get(reverse('bookings:list'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

    def test_booking_list_view(self):
        """Test booking list view displays bookings"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('bookings:list'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/booking_list.html')
        self.assertIn('page_obj', response.context)
        self.assertIn('filter_form', response.context)
        self.assertEqual(response.context['page_obj'].paginator.count, 2)

    def test_booking_list_filter_by_status(self):
        """Test filtering bookings by status"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('bookings:list'), {'status': 'planned'})

        self.assertEqual(response.status_code, 200)
        bookings = list(response.context['page_obj'])
        self.assertEqual(len(bookings), 1)
        self.assertEqual(bookings[0].status, 'planned')

    def test_booking_list_filter_by_type_income(self):
        """Test filtering bookings by type (income)"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('bookings:list'), {'type': 'income'})

        self.assertEqual(response.status_code, 200)
        bookings = list(response.context['page_obj'])
        self.assertEqual(len(bookings), 1)
        self.assertTrue(bookings[0].amount >= 0)

    def test_booking_list_filter_by_type_expense(self):
        """Test filtering bookings by type (expense)"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('bookings:list'), {'type': 'expense'})

        self.assertEqual(response.status_code, 200)
        bookings = list(response.context['page_obj'])
        self.assertEqual(len(bookings), 1)
        self.assertTrue(bookings[0].amount < 0)

    def test_booking_list_filter_by_category(self):
        """Test filtering bookings by category"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('bookings:list'), {'category': self.category.id})

        self.assertEqual(response.status_code, 200)
        bookings = list(response.context['page_obj'])
        self.assertEqual(len(bookings), 2)

    def test_booking_create_get(self):
        """Test GET request to create booking"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('bookings:create'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/booking_form.html')
        self.assertIn('form', response.context)

    def test_booking_create_post(self):
        """Test POST request to create booking"""
        self.client.login(username='testuser', password='testpass123')

        data = {
            'date': '2025-02-01',
            'description': 'Neue Buchung',
            'amount': '750.00',
            'category': self.category.id,
            'status': 'planned',
            'notes': 'Test note'
        }

        response = self.client.post(reverse('bookings:create'), data)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Booking.objects.filter(description='Neue Buchung').exists())

        new_booking = Booking.objects.get(description='Neue Buchung')
        self.assertEqual(new_booking.amount, Decimal('750.00'))
        self.assertEqual(new_booking.category, self.category)

    def test_booking_edit_get(self):
        """Test GET request to edit booking"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('bookings:edit', args=[self.booking1.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/booking_form.html')
        self.assertIn('form', response.context)
        self.assertEqual(response.context['booking'], self.booking1)

    def test_booking_edit_post(self):
        """Test POST request to edit booking"""
        self.client.login(username='testuser', password='testpass123')

        data = {
            'date': '2025-02-15',
            'description': 'Geänderte Buchung',
            'amount': '1500.00',
            'category': self.category.id,
            'status': 'booked',
            'notes': 'Updated note'
        }

        response = self.client.post(reverse('bookings:edit', args=[self.booking1.id]), data)

        self.assertEqual(response.status_code, 302)

        self.booking1.refresh_from_db()
        self.assertEqual(self.booking1.description, 'Geänderte Buchung')
        self.assertEqual(self.booking1.amount, Decimal('1500.00'))
        self.assertEqual(self.booking1.status, 'booked')

    def test_booking_delete(self):
        """Test deleting a booking"""
        self.client.login(username='testuser', password='testpass123')
        booking_id = self.booking1.id

        response = self.client.post(reverse('bookings:delete', args=[booking_id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Booking.objects.filter(id=booking_id).exists())

    def test_booking_delete_only_post(self):
        """Test that delete only accepts POST requests"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('bookings:delete', args=[self.booking1.id]))

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Booking.objects.filter(id=self.booking1.id).exists())

    def test_booking_toggle_status_planned_to_booked(self):
        """Test toggling status from planned to booked"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('bookings:toggle_status', args=[self.booking1.id]))

        self.assertEqual(response.status_code, 200)
        self.booking1.refresh_from_db()
        self.assertEqual(self.booking1.status, 'booked')

    def test_booking_toggle_status_booked_to_planned(self):
        """Test toggling status from booked to planned"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('bookings:toggle_status', args=[self.booking2.id]))

        self.assertEqual(response.status_code, 200)
        self.booking2.refresh_from_db()
        self.assertEqual(self.booking2.status, 'planned')

    def test_booking_toggle_status_only_post(self):
        """Test that toggle status only accepts POST requests"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('bookings:toggle_status', args=[self.booking1.id]))

        self.assertEqual(response.status_code, 405)

    def test_pagination(self):
        """Test pagination with more than 50 bookings"""
        self.client.login(username='testuser', password='testpass123')

        # Create 60 bookings
        for i in range(60):
            Booking.objects.create(
                date=date(2025, 1, 1),
                description=f'Booking {i}',
                amount=Decimal('100.00'),
                status='planned',
                category=self.category
            )

        response = self.client.get(reverse('bookings:list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 50)
        self.assertTrue(response.context['page_obj'].has_next())

        # Test page 2
        response = self.client.get(reverse('bookings:list'), {'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 12)  # 60 + 2 original = 62 total


class BookingFormTestCase(TestCase):
    """Test cases for booking forms"""

    def setUp(self):
        """Set up test data"""
        self.category = Category.objects.create(
            name='Test Kategorie',
            icon='wallet',
            color='#007bff'
        )

    def test_booking_form_valid(self):
        """Test booking form with valid data"""
        form_data = {
            'date': date(2025, 1, 15),
            'description': 'Test Booking',
            'amount': Decimal('100.00'),
            'category': self.category.id,
            'status': 'planned',
            'notes': 'Test notes'
        }

        form = BookingForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_booking_form_missing_required_fields(self):
        """Test booking form with missing required fields"""
        form_data = {
            'description': 'Test Booking'
        }

        form = BookingForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('date', form.errors)
        self.assertIn('amount', form.errors)
        self.assertIn('category', form.errors)
        self.assertIn('status', form.errors)

    def test_booking_form_negative_amount(self):
        """Test booking form with negative amount"""
        form_data = {
            'date': date(2025, 1, 15),
            'description': 'Test Expense',
            'amount': Decimal('-500.00'),
            'category': self.category.id,
            'status': 'planned',
        }

        form = BookingForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_booking_filter_form_all_empty(self):
        """Test filter form with all empty values"""
        form = BookingFilterForm(data={})
        self.assertTrue(form.is_valid())

    def test_booking_filter_form_with_filters(self):
        """Test filter form with filter values"""
        form_data = {
            'status': 'planned',
            'type': 'income',
            'category': self.category.id
        }

        form = BookingFilterForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['status'], 'planned')
        self.assertEqual(form.cleaned_data['type'], 'income')
        self.assertEqual(form.cleaned_data['category'], self.category)


class BookingDuplicateTestCase(TestCase):
    """Test cases for booking duplicate functionality"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        # Create test category
        self.category = Category.objects.create(
            name='Test Kategorie',
            icon='wallet',
            color='#007bff'
        )

        # Create test series
        self.series = RecurringSeries.objects.create(
            description='Test Serie',
            amount=Decimal('100.00'),
            interval='monthly',
            start_date=date(2025, 1, 1),
            category=self.category
        )

        # Create test booking with series
        self.booking_with_series = Booking.objects.create(
            date=date(2025, 1, 15),
            description='Test Booking',
            amount=Decimal('1000.00'),
            status='booked',
            category=self.category,
            series=self.series,
            notes='Test notes'
        )

        # Create standalone booking
        self.standalone_booking = Booking.objects.create(
            date=date(2025, 1, 20),
            description='Standalone Booking',
            amount=Decimal('-500.00'),
            status='planned',
            category=self.category,
            notes='Some notes'
        )

    def test_duplicate_requires_login(self):
        """Test that duplicate requires login"""
        response = self.client.post(reverse('bookings:duplicate', args=[self.booking_with_series.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

    def test_duplicate_only_post(self):
        """Test that duplicate only accepts POST requests"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('bookings:duplicate', args=[self.booking_with_series.id]))

        self.assertEqual(response.status_code, 405)

    def test_duplicate_creates_new_booking(self):
        """Test that duplicate creates a new booking"""
        self.client.login(username='testuser', password='testpass123')
        initial_count = Booking.objects.count()

        response = self.client.post(reverse('bookings:duplicate', args=[self.booking_with_series.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Booking.objects.count(), initial_count + 1)

    def test_duplicate_copies_fields_correctly(self):
        """Test that duplicate copies the right fields"""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(reverse('bookings:duplicate', args=[self.booking_with_series.id]))

        # Get the newly created booking (last one)
        new_booking = Booking.objects.order_by('-id').first()

        # Check copied fields
        self.assertEqual(new_booking.description, self.booking_with_series.description)
        self.assertEqual(new_booking.amount, self.booking_with_series.amount)
        self.assertEqual(new_booking.category, self.booking_with_series.category)
        self.assertEqual(new_booking.notes, self.booking_with_series.notes)

        # Check changed fields
        self.assertEqual(new_booking.date, date.today())
        self.assertEqual(new_booking.status, 'planned')
        self.assertIsNone(new_booking.series)  # Series should not be copied

    def test_duplicate_does_not_copy_series(self):
        """Test that duplicate does not copy series reference"""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(reverse('bookings:duplicate', args=[self.booking_with_series.id]))

        new_booking = Booking.objects.order_by('-id').first()
        self.assertIsNone(new_booking.series)

    def test_duplicate_returns_form_with_is_duplicate_flag(self):
        """Test that duplicate returns form with is_duplicate flag"""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(reverse('bookings:duplicate', args=[self.standalone_booking.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIn('is_duplicate', response.context)
        self.assertTrue(response.context['is_duplicate'])
        self.assertIn('booking', response.context)
        self.assertIn('form', response.context)

    def test_duplicate_standalone_booking(self):
        """Test duplicating a standalone booking (without series)"""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(reverse('bookings:duplicate', args=[self.standalone_booking.id]))

        new_booking = Booking.objects.order_by('-id').first()

        self.assertEqual(new_booking.description, self.standalone_booking.description)
        self.assertEqual(new_booking.amount, self.standalone_booking.amount)
        self.assertEqual(new_booking.category, self.standalone_booking.category)
        self.assertEqual(new_booking.notes, self.standalone_booking.notes)
        self.assertEqual(new_booking.date, date.today())
        self.assertEqual(new_booking.status, 'planned')
        self.assertIsNone(new_booking.series)

    def test_duplicate_htmx_request(self):
        """Test duplicate with HTMX request"""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(
            reverse('bookings:duplicate', args=[self.standalone_booking.id]),
            HTTP_HX_REQUEST='true'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/_booking_form.html')

    def test_duplicate_nonexistent_booking(self):
        """Test duplicating a non-existent booking"""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post(reverse('bookings:duplicate', args=[99999]))

        self.assertEqual(response.status_code, 404)
