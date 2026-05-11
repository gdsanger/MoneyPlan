from django.urls import path
from . import views

urlpatterns = [
    path('', views.category_list, name='category_list'),
    path('neu/', views.category_create, name='category_create'),
    path('<int:category_id>/bearbeiten/', views.category_edit, name='category_edit'),
    path('<int:category_id>/loeschen/', views.category_delete, name='category_delete'),
]
