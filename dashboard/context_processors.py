"""
Context processors for dashboard app.
"""
from alerts.models import Alert
from datetime import date


def alert_count(request):
    """
    Add active alerts count to all templates.
    Also adds has_critical_alerts flag for critical alerts (overdue or liquidity).
    Also adds task counts for navbar badge.
    """
    if request.user.is_authenticated:
        # Alert counts
        count = Alert.objects.count()
        critical_count = Alert.objects.filter(
            alert_type__in=['overdue', 'liquidity']
        ).count()
        has_critical = critical_count > 0

        # Task counts
        from tasks.models import Task
        today = date.today()
        overdue_tasks = Task.objects.filter(
            status='open',
            due_date__lt=today
        ).count()
        due_today_tasks = Task.objects.filter(
            status='open',
            due_date=today
        ).count()
        task_badge_count = overdue_tasks + due_today_tasks
    else:
        count = 0
        has_critical = False
        task_badge_count = 0

    return {
        'active_alerts_count': count,
        'has_critical_alerts': has_critical,
        'task_badge_count': task_badge_count,
    }
