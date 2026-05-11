from django.urls import path
from . import views

app_name = 'ai'

urlpatterns = [
    path('einstellungen/', views.ai_settings, name='settings'),
    path('einstellungen/verbindung-testen/', views.test_connection, name='test_connection'),
]
