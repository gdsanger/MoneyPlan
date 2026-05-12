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

    # Client URLs
    path('kunden/', views.client_list, name='client_list'),
    path('kunden/neu/', views.client_create, name='client_create'),
    path('kunden/<int:client_id>/bearbeiten/', views.client_edit, name='client_edit'),
    path('kunden/<int:client_id>/loeschen/', views.client_delete, name='client_delete'),
]
