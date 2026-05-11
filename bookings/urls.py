from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    path('', views.booking_list, name='list'),
    path('categories/', views.category_list, name='categories'),
    path('series/', views.series_list, name='series'),
]
