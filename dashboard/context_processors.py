"""
Context processors for dashboard app.
"""
from alerts.models import Alert


def alert_count(request):
    """
    Add active alerts count to all templates.
    Also adds has_critical_alerts flag for critical alerts (overdue or liquidity).
    """
    if request.user.is_authenticated:
        count = Alert.objects.count()
        critical_count = Alert.objects.filter(
            alert_type__in=['overdue', 'liquidity']
        ).count()
        has_critical = critical_count > 0
    else:
        count = 0
        has_critical = False

    return {
        'active_alerts_count': count,
        'has_critical_alerts': has_critical,
    }
