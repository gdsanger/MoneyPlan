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
    path('series/', views.series_list, name='series'),
    path('monate/', views.month_view, name='month_view'),
    path('monate/<int:year>/<int:month>/', views.month_view, name='month_view_detail'),
]
