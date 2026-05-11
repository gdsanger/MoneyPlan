from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    path('', views.booking_list, name='list'),
    path('neu/', views.booking_create, name='create'),
    path('<int:booking_id>/bearbeiten/', views.booking_edit, name='edit'),
    path('<int:booking_id>/loeschen/', views.booking_delete, name='delete'),
    path('<int:booking_id>/status/', views.booking_toggle_status, name='toggle_status'),
    path('categories/', views.category_list, name='categories'),
    path('categories/neu/', views.category_create, name='category_create'),
    path('categories/<int:category_id>/bearbeiten/', views.category_edit, name='category_edit'),
    path('categories/<int:category_id>/loeschen/', views.category_delete, name='category_delete'),
    path('series/', views.series_list, name='series'),
]
