from django.urls import path
from . import views

app_name = 'tags'

urlpatterns = [
    path('', views.tag_list, name='list'),
    path('auswertung/', views.tag_overview, name='overview'),
    path('neu/', views.tag_create, name='create'),
    path('<int:tag_id>/bearbeiten/', views.tag_edit, name='edit'),
    path('<int:tag_id>/loeschen/', views.tag_delete, name='delete'),
    path('<int:tag_id>/archivieren/', views.tag_toggle_archived, name='toggle_archived'),
]
