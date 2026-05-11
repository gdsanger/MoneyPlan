"""
Context processors for dashboard app.
"""
from alerts.models import Alert


def alert_count(request):
    """
    Add active alerts count to all templates.
    """
    if request.user.is_authenticated:
        count = Alert.objects.count()
    else:
        count = 0

    return {
        'active_alerts_count': count
    }
