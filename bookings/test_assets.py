from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date
from bookings.models import Asset
from bookings.services import get_total_assets, get_net_worth, get_assets_by_category


class AssetModelTestCase(TestCase):
    """Tests for Asset model"""

    def test_asset_creation(self):
        """Test creating an asset"""
        asset = Asset.objects.create(
            name="Test Immobilie",
            description="Test property description",
            category="real_estate",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal('250000.00'),
            current_value=Decimal('280000.00')
        )
        self.assertEqual(asset.name, "Test Immobilie")
        self.assertEqual(asset.category, "real_estate")
        self.assertEqual(asset.current_value, Decimal('280000.00'))

    def test_value_change_calculation(self):
        """Test value_change property calculation"""
        asset = Asset.objects.create(
            name="Test Asset",
            category="vehicle",
            purchase_price=Decimal('30000.00'),
            current_value=Decimal('25000.00')
        )
        # Should show a loss
        self.assertEqual(asset.value_change, Decimal('-5000.00'))

    def test_value_change_percent_calculation(self):
        """Test value_change_percent property calculation"""
        asset = Asset.objects.create(
            name="Test Asset",
            category="vehicle",
            purchase_price=Decimal('30000.00'),
            current_value=Decimal('33000.00')
        )
        # 10% gain
        self.assertEqual(asset.value_change_percent, Decimal('10.0'))

    def test_value_change_none_when_no_purchase_price(self):
        """Test value_change returns None when no purchase price"""
        asset = Asset.objects.create(
            name="Test Asset",
            category="bank_account",
            current_value=Decimal('50000.00')
        )
        self.assertIsNone(asset.value_change)
        self.assertIsNone(asset.value_change_percent)

    def test_asset_ordering(self):
        """Test assets are ordered by current_value descending"""
        Asset.objects.create(
            name="Small Asset",
            category="electronics",
            current_value=Decimal('500.00')
        )
        Asset.objects.create(
            name="Large Asset",
            category="real_estate",
            current_value=Decimal('300000.00')
        )
        Asset.objects.create(
            name="Medium Asset",
            category="vehicle",
            current_value=Decimal('25000.00')
        )

        assets = list(Asset.objects.all())
        self.assertEqual(assets[0].name, "Large Asset")
        self.assertEqual(assets[1].name, "Medium Asset")
        self.assertEqual(assets[2].name, "Small Asset")


class AssetServiceTestCase(TestCase):
    """Tests for asset service functions"""

    def setUp(self):
        """Set up test assets"""
        Asset.objects.create(
            name="Real Estate",
            category="real_estate",
            current_value=Decimal('280000.00')
        )
        Asset.objects.create(
            name="Vehicle",
            category="vehicle",
            current_value=Decimal('25000.00')
        )

    def test_get_total_assets(self):
        """Test total assets calculation"""
        total = get_total_assets()
        self.assertEqual(total, Decimal('305000.00'))

    def test_get_total_assets_empty(self):
        """Test total assets when no assets exist"""
        Asset.objects.all().delete()
        total = get_total_assets()
        self.assertEqual(total, Decimal('0.00'))

    def test_get_net_worth(self):
        """Test net worth calculation (no liabilities)"""
        net_worth = get_net_worth()
        # No liabilities, so net worth = total assets
        self.assertEqual(net_worth, Decimal('305000.00'))

    def test_get_assets_by_category(self):
        """Test assets grouped by category"""
        categories = get_assets_by_category()

        self.assertEqual(len(categories), 2)

        # First category should be real_estate (highest value)
        self.assertEqual(categories[0]['category'], 'real_estate')
        self.assertEqual(categories[0]['label'], 'Immobilien')
        self.assertEqual(categories[0]['total'], Decimal('280000.00'))
        self.assertEqual(categories[0]['count'], 1)
        self.assertAlmostEqual(categories[0]['percent'], 91.8, places=1)

        # Second category should be vehicle
        self.assertEqual(categories[1]['category'], 'vehicle')
        self.assertEqual(categories[1]['label'], 'Fahrzeuge')
        self.assertEqual(categories[1]['total'], Decimal('25000.00'))
        self.assertEqual(categories[1]['count'], 1)
        self.assertAlmostEqual(categories[1]['percent'], 8.2, places=1)


class AssetViewTestCase(TestCase):
    """Tests for asset views"""

    def setUp(self):
        """Set up test user and assets"""
        self.user = User.objects.create_user('testuser', 'test@test.com', 'password123')
        self.client = Client()
        self.client.login(username='testuser', password='password123')

        self.asset = Asset.objects.create(
            name="Test Asset",
            category="real_estate",
            purchase_price=Decimal('250000.00'),
            current_value=Decimal('280000.00')
        )

    def test_asset_list_view(self):
        """Test asset list view loads correctly"""
        response = self.client.get(reverse('bookings:asset_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Asset')
        self.assertContains(response, 'Gesamtvermögen')
        self.assertContains(response, 'Nettovermögen')

    def test_asset_create_view_get(self):
        """Test asset create form loads"""
        response = self.client.get(reverse('bookings:asset_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vermögensgegenstand')

    def test_asset_create_view_post(self):
        """Test creating an asset via POST"""
        data = {
            'name': 'New Asset',
            'category': 'vehicle',
            'current_value': '30000.00',
        }
        response = self.client.post(reverse('bookings:asset_create'), data)
        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Asset should be created
        self.assertTrue(Asset.objects.filter(name='New Asset').exists())

    def test_asset_edit_view_get(self):
        """Test asset edit form loads"""
        response = self.client.get(reverse('bookings:asset_edit', args=[self.asset.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Asset')

    def test_asset_edit_view_post(self):
        """Test editing an asset via POST"""
        data = {
            'name': 'Updated Asset Name',
            'category': 'real_estate',
            'current_value': '290000.00',
        }
        response = self.client.post(
            reverse('bookings:asset_edit', args=[self.asset.id]),
            data
        )
        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Asset should be updated
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.name, 'Updated Asset Name')
        self.assertEqual(self.asset.current_value, Decimal('290000.00'))

    def test_asset_delete_view(self):
        """Test deleting an asset"""
        response = self.client.post(reverse('bookings:asset_delete', args=[self.asset.id]))
        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Asset should be deleted
        self.assertFalse(Asset.objects.filter(id=self.asset.id).exists())

    def test_asset_update_value_view(self):
        """Test quick value update via HTMX"""
        data = {'current_value': '285000.00'}
        response = self.client.post(
            reverse('bookings:asset_update_value', args=[self.asset.id]),
            data,
            HTTP_HX_REQUEST='true'
        )
        self.assertEqual(response.status_code, 200)

        # Asset value should be updated
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.current_value, Decimal('285000.00'))
