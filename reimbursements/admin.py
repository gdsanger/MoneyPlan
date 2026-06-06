from django.contrib import admin
from .models import ReimbursementConfig, ExpenseClaim, ReimbursementSubmission


@admin.register(ReimbursementConfig)
class ReimbursementConfigAdmin(admin.ModelAdmin):
    list_display = ('employee_name', 'recipient_email', 'place', 'logo', 'signature_image')


@admin.register(ExpenseClaim)
class ExpenseClaimAdmin(admin.ModelAdmin):
    list_display = ('date', 'description', 'amount', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('description', 'notes')


@admin.register(ReimbursementSubmission)
class ReimbursementSubmissionAdmin(admin.ModelAdmin):
    list_display = ('submitted_at', 'total_amount')
    filter_horizontal = ('claims',)
