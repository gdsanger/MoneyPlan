"""URL patterns for reimbursements."""
from django.urls import path
from . import views

app_name = 'reimbursements'

urlpatterns = [
    path('', views.claim_list, name='list'),
    path('beleg-upload/', views.receipt_upload, name='receipt_upload'),
    path('beleg-bestaetigen/', views.receipt_confirm, name='receipt_confirm'),
    path('pdf-vorschau/', views.pdf_preview, name='pdf_preview'),
    path('einreichen/', views.submit_claims, name='submit'),
    path('einstellungen/', views.settings_view, name='settings'),
    path('<int:claim_id>/bearbeiten/', views.claim_edit, name='edit'),
    path('<int:claim_id>/loeschen/', views.claim_delete, name='delete'),
    path('<int:claim_id>/erstattet/', views.claim_toggle_reimbursed, name='toggle_reimbursed'),
]
