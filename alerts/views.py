from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Alert


@login_required
def alert_list(request):
    """Liste aller Alerts"""
    alerts = Alert.objects.all()
    return render(request, 'alerts/alert_list.html', {'alerts': alerts})
