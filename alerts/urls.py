from django.urls import path
from . import views

app_name = 'alerts'

urlpatterns = [
    path('', views.alert_list, name='list'),
    path('einstellungen/', views.alert_settings, name='settings'),
    path('test-mail/', views.test_mail, name='test_mail'),
]
