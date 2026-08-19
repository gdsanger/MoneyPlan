from django.contrib import admin
from .models import Category, RecurringSeries, Booking, Liability, Asset, ReconciliationLog, Account, AccountBalance


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category_type', 'icon', 'color', 'description']
    list_filter = ['category_type']
    search_fields = ['name', 'description']


@admin.register(RecurringSeries)
class RecurringSeriesAdmin(admin.ModelAdmin):
    list_display = ['description', 'amount', 'interval', 'start_date', 'end_date', 'category', 'archived']
    list_filter = ['interval', 'category', 'archived']
    search_fields = ['description']
    date_hierarchy = 'start_date'


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['date', 'description', 'amount', 'status', 'category', 'series']
    list_filter = ['status', 'category', 'date']
    search_fields = ['description', 'notes']
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Liability)
class LiabilityAdmin(admin.ModelAdmin):
    list_display = ['name', 'initial_amount', 'start_date', 'due_date', 'category']
    list_filter = ['category']
    search_fields = ['name', 'description', 'notes']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'start_date'


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'purchase_price', 'current_value', 'value_change', 'last_updated']
    list_filter = ['category']
    search_fields = ['name', 'description', 'notes']
    readonly_fields = ['last_updated', 'created_at']


@admin.register(ReconciliationLog)
class ReconciliationLogAdmin(admin.ModelAdmin):
    list_display = ['date', 'actual_balance', 'expected_balance', 'difference', 'booking']
    readonly_fields = ['created_at']
    date_hierarchy = 'date'


class AccountBalanceInline(admin.TabularInline):
    model = AccountBalance
    extra = 0
    fields = ['date', 'balance', 'note']


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['name', 'account_type', 'is_active', 'sort_order', 'latest_balance']
    list_filter = ['account_type', 'is_active']
    search_fields = ['name']
    inlines = [AccountBalanceInline]


@admin.register(AccountBalance)
class AccountBalanceAdmin(admin.ModelAdmin):
    list_display = ['account', 'date', 'balance', 'note']
    list_filter = ['account', 'date']
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at']


