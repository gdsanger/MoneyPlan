from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    path('', views.booking_list, name='list'),
    path('neu/', views.booking_create, name='create'),
    path('schnell/', views.quick_create, name='quick_create'),
    path('beleg-upload/', views.receipt_upload, name='receipt_upload'),
    path('beleg-bestaetigen/', views.receipt_confirm, name='receipt_confirm'),
    path('<int:booking_id>/bearbeiten/', views.booking_edit, name='edit'),
    path('<int:booking_id>/loeschen/', views.booking_delete, name='delete'),
    path('<int:booking_id>/status/', views.booking_toggle_status, name='toggle_status'),
    path('<int:booking_id>/duplizieren/', views.booking_duplicate, name='duplicate'),
    path('series/', views.series_list, name='series'),
    path('categories/', views.category_list, name='categories'),
    path('serien/', views.series_list, name='series_list'),
    path('serien/neu/', views.series_wizard, name='series_wizard'),
    path('serien/neu/vorschau/', views.series_preview, name='series_preview'),
    path('serien/neu/bestaetigen/', views.series_confirm, name='series_confirm'),
    path('serien/<int:series_id>/loeschen/', views.series_delete, name='series_delete'),
    path('monate/', views.month_view, name='month_view'),
    path('monate/<int:year>/<int:month>/', views.month_view, name='month_view_detail'),
    # Liability URLs
    path('verbindlichkeiten/', views.liability_list, name='liability_list'),
    path('verbindlichkeiten/neu/', views.liability_create, name='liability_create'),
    path('verbindlichkeiten/<int:liability_id>/', views.liability_detail, name='liability_detail'),
    path('verbindlichkeiten/<int:liability_id>/bearbeiten/', views.liability_edit, name='liability_edit'),
    path('verbindlichkeiten/<int:liability_id>/loeschen/', views.liability_delete, name='liability_delete'),
    # Asset URLs
    path('vermoegen/', views.asset_list, name='asset_list'),
    path('vermoegen/neu/', views.asset_create, name='asset_create'),
    path('vermoegen/<int:asset_id>/bearbeiten/', views.asset_edit, name='asset_edit'),
    path('vermoegen/<int:asset_id>/loeschen/', views.asset_delete, name='asset_delete'),
    path('vermoegen/<int:asset_id>/wert-aktualisieren/', views.asset_update_value, name='asset_update_value'),
]
