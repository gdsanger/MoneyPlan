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


# URL-Namen je Navigations-Bereich. "Buchungen" und "Finanzen" leben beide im
# bookings-Namespace, daher reicht der Namespace allein nicht zur Abgrenzung.
_NAV_BUCHUNGEN_NAMES = {
    'bookings:list', 'bookings:create', 'bookings:quick_create',
    'bookings:receipt_upload', 'bookings:receipt_confirm', 'bookings:edit',
    'bookings:delete', 'bookings:toggle_status', 'bookings:duplicate',
    'bookings:series', 'bookings:categories', 'bookings:series_list',
    'bookings:series_wizard', 'bookings:series_preview', 'bookings:series_confirm',
    'bookings:series_delete', 'bookings:month_view', 'bookings:month_view_detail',
    'dashboard:year_overview', 'dashboard:year_overview_detail',
}
_NAV_FINANZEN_NAMES = {
    'bookings:liability_list', 'bookings:liability_create', 'bookings:liability_detail',
    'bookings:liability_edit', 'bookings:liability_delete',
    'bookings:asset_list', 'bookings:asset_create', 'bookings:asset_edit',
    'bookings:asset_delete', 'bookings:asset_update_value',
    'bookings:reconciliation', 'bookings:reconciliation_create',
    'alerts:list', 'alerts:test_mail',
}
_NAV_SONSTIGES_NAMESPACES = {'tasks', 'timetracking', 'reimbursements', 'tags'}


def nav_active_section(request):
    """
    Bestimmt den aktuell aktiven Navigationsbereich anhand des Resolver-Matches,
    damit die Navbar (base.html) den passenden Menüpunkt hervorheben kann.
    """
    match = getattr(request, 'resolver_match', None)
    if match is None:
        return {'nav_active_view': None, 'nav_active_section': None}

    view_name = match.view_name
    section = None

    if view_name == 'dashboard:index':
        section = 'dashboard'
    elif view_name in _NAV_BUCHUNGEN_NAMES:
        section = 'buchungen'
    elif view_name in _NAV_FINANZEN_NAMES:
        section = 'finanzen'
    elif match.namespace in _NAV_SONSTIGES_NAMESPACES:
        section = 'sonstiges'

    return {
        'nav_active_view': view_name,
        'nav_active_section': section,
    }
