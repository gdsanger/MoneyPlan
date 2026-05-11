from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    path('', views.task_list, name='list'),
    path('neu/', views.task_create, name='create'),
    path('<int:task_id>/bearbeiten/', views.task_edit, name='edit'),
    path('<int:task_id>/loeschen/', views.task_delete, name='delete'),
    path('<int:task_id>/erledigt/', views.task_toggle_done, name='toggle_done'),
]
