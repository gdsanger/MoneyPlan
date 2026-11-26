"""URL patterns for time tracking."""
from django.urls import path
from . import views

app_name = 'timetracking'

urlpatterns = [
    # Time entry URLs
    path('', views.time_entry_list, name='list'),
    path('neu/', views.time_entry_create, name='create'),
    path('<int:entry_id>/bearbeiten/', views.time_entry_edit, name='edit'),
    path('<int:entry_id>/loeschen/', views.time_entry_delete, name='delete'),
    path('<int:entry_id>/abgerechnet/', views.time_entry_toggle_billed, name='toggle_billed'),
    path('bulk-tag/', views.time_entry_bulk_tag, name='bulk_tag'),

    # Minijob (reiner Zeitnachweis)
    path('minijob/', views.minijob_month, name='minijob'),
    path('minijob/neu/', views.minijob_shift_create, name='minijob_create'),
    path('minijob/<int:shift_id>/bearbeiten/', views.minijob_shift_edit, name='minijob_edit'),
    path('minijob/<int:shift_id>/loeschen/', views.minijob_shift_delete, name='minijob_delete'),
    path('minijob/einstellungen/', views.minijob_settings, name='minijob_settings'),
    path('minijob/export.csv', views.minijob_export_csv, name='minijob_export'),

    # Client URLs
    path('kunden/', views.client_list, name='client_list'),
    path('kunden/neu/', views.client_create, name='client_create'),
    path('kunden/<int:client_id>/bearbeiten/', views.client_edit, name='client_edit'),
    path('kunden/<int:client_id>/loeschen/', views.client_delete, name='client_delete'),
]
