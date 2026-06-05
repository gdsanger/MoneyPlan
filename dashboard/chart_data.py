"""
Chart data endpoints for dashboard.
Returns JSON for Chart.js consumption.
"""
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from bookings.services import get_forecast, get_top_categories, get_bookings_for_month
from datetime import date


@login_required
def forecast_chart_data(request):
    """
    Return forecast data for line chart.
    Shows current balance progression + future months forecast.
    Includes time tracking annotations in tooltip data.
    """
    forecast_data = get_forecast(months=settings.FORECAST_MONTHS)

    labels = [item['label'] for item in forecast_data]
    balances = [float(item['projected_balance']) for item in forecast_data]

    # Create tooltip labels with time tracking info
    tooltip_labels = []
    for item in forecast_data:
        label = item['label']
        if 'timetracking_amount' in item:
            tt_amount = float(item['timetracking_amount'])
            label += f" (inkl. ⏱ Stundenabrechnung: +{tt_amount:.2f} €)"
        tooltip_labels.append(label)

    end_balance = forecast_data[-1]['projected_balance']
    min_entry = min(forecast_data, key=lambda item: item['projected_balance'])

    data = {
        'labels': labels,
        'tooltipLabels': tooltip_labels,
        'currentMonthIndex': 0,
        'summary': {
            'endBalance': float(end_balance),
            'endLabel': forecast_data[-1]['label'],
            'minBalance': float(min_entry['projected_balance']),
            'minLabel': min_entry['label'],
        },
        'datasets': [{
            'label': 'Saldoverlauf',
            'data': balances,
            'borderColor': 'rgba(13, 202, 240, 1)',
            'backgroundColor': 'rgba(13, 202, 240, 0.15)',
            'tension': 0.1,
            'fill': True,
            'pointRadius': 5,
            'pointHoverRadius': 7,
        }]
    }

    return JsonResponse(data)


@login_required
def category_chart_data(request):
    """
    Return top categories data for horizontal bar chart.
    Shows top 10 expense categories from last 3 months.
    """
    top_categories = get_top_categories(limit=10, months_back=3)

    labels = [item['category'].name for item in top_categories]
    amounts = [float(item['total']) for item in top_categories]
    colors = [item['category'].color for item in top_categories]

    data = {
        'labels': labels,
        'datasets': [{
            'label': 'Ausgaben (EUR)',
            'data': amounts,
            'backgroundColor': colors,
            'borderColor': colors,
            'borderWidth': 1
        }]
    }

    return JsonResponse(data)


@login_required
def donut_chart_data(request):
    """
    Return income vs expenses for current month as doughnut chart data.
    """
    today = date.today()
    bookings = get_bookings_for_month(today.year, today.month)

    # Calculate income and expenses for current month
    total_income = sum(
        b.amount for b in bookings
        if b.amount > 0
    )
    total_expenses = sum(
        abs(b.amount) for b in bookings
        if b.amount < 0
    )

    data = {
        'labels': ['Einnahmen', 'Ausgaben'],
        'datasets': [{
            'data': [float(total_income), float(total_expenses)],
            'backgroundColor': [
                'rgba(40, 167, 69, 0.8)',   # green for income
                'rgba(220, 53, 69, 0.8)'    # red for expenses
            ],
            'borderColor': [
                'rgba(40, 167, 69, 1)',
                'rgba(220, 53, 69, 1)'
            ],
            'borderWidth': 1
        }]
    }

    return JsonResponse(data)
