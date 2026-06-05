from django.urls import path
from . import views, chart_data

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/forecast/', chart_data.forecast_chart_data, name='forecast_data'),
    path('api/categories/', chart_data.category_chart_data, name='category_data'),
    path('api/donut/', chart_data.donut_chart_data, name='donut_data'),
    path('mark-as-booked/<int:booking_id>/', views.mark_as_booked, name='mark_as_booked'),
    path('jahresuebersicht/', views.year_overview, name='year_overview'),
    path('jahresuebersicht/<int:year>/', views.year_overview, name='year_overview_detail'),
    path('finanzueberblick/', views.financial_overview, name='financial_overview'),
]
