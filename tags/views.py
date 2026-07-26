from calendar import monthrange
from datetime import date, datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Count

from .models import Tag
from .forms import TagForm
from .services import get_tag_overview


@login_required
def tag_list(request):
    """Liste aller Tags, gruppiert nach Dimension."""
    tags = Tag.objects.annotate(
        booking_count=Count('bookings', distinct=True),
        time_entry_count=Count('time_entries', distinct=True),
    ).order_by('archived', 'kind', 'name')

    context = {
        'active_tags': tags.filter(archived=False),
        'archived_tags': tags.filter(archived=True),
        'total_tags': tags.count(),
    }

    return render(request, 'tags/tag_list.html', context)


@login_required
def tag_create(request):
    """Erstelle einen neuen Tag"""
    if request.method == 'POST':
        form = TagForm(request.POST)
        if form.is_valid():
            tag = form.save()

            if request.htmx:
                response = HttpResponse('')
                response['HX-Redirect'] = request.META.get('HTTP_REFERER', '/tags/')
                return response

            messages.success(request, f'Tag "{tag.name}" wurde erstellt.')
            return redirect('tags:list')
    else:
        form = TagForm()

    context = {'form': form}

    if request.htmx:
        return render(request, 'tags/_tag_form.html', context)

    return render(request, 'tags/tag_form.html', context)


@login_required
def tag_edit(request, tag_id):
    """Bearbeite einen Tag"""
    tag = get_object_or_404(Tag, pk=tag_id)

    if request.method == 'POST':
        form = TagForm(request.POST, instance=tag)
        if form.is_valid():
            tag = form.save()

            if request.htmx:
                response = HttpResponse('')
                response['HX-Redirect'] = request.META.get('HTTP_REFERER', '/tags/')
                return response

            messages.success(request, f'Tag "{tag.name}" wurde aktualisiert.')
            return redirect('tags:list')
    else:
        form = TagForm(instance=tag)

    context = {
        'form': form,
        'tag': tag,
    }

    if request.htmx:
        return render(request, 'tags/_tag_form.html', context)

    return render(request, 'tags/tag_form.html', context)


@login_required
def tag_delete(request, tag_id):
    """Lösche einen Tag, nur wenn er nicht verwendet wird"""
    if request.method != 'POST':
        return HttpResponse(status=405)

    tag = get_object_or_404(Tag, pk=tag_id)

    usage_count = tag.bookings.count() + tag.time_entries.count()
    if usage_count > 0:
        error_message = (
            f'Tag "{tag.name}" kann nicht gelöscht werden. '
            f'Er ist noch {usage_count} Buchung{"en" if usage_count != 1 else ""}/Zeiteintrag{"en" if usage_count != 1 else ""} zugeordnet.'
        )
        if request.htmx:
            return HttpResponse(f'<div class="alert alert-danger">{error_message}</div>', status=400)
        messages.error(request, error_message)
        return redirect('tags:list')

    tag_name = tag.name
    tag.delete()

    if request.htmx:
        return HttpResponse('')

    messages.success(request, f'Tag "{tag_name}" wurde gelöscht.')
    return redirect('tags:list')


@login_required
def tag_toggle_archived(request, tag_id):
    """Archiviere einen Tag bzw. hole ihn aus dem Archiv zurück"""
    if request.method != 'POST':
        return HttpResponse(status=405)

    tag = get_object_or_404(Tag, pk=tag_id)
    tag.archived = not tag.archived
    tag.save(update_fields=['archived'])

    if request.htmx:
        response = HttpResponse('')
        response['HX-Redirect'] = request.META.get('HTTP_REFERER', '/tags/')
        return response

    if tag.archived:
        messages.success(request, f'Tag "{tag.name}" wurde archiviert.')
    else:
        messages.success(request, f'Tag "{tag.name}" wurde wiederhergestellt.')
    return redirect('tags:list')


def _parse_overview_period(request):
    """
    Resolve the requested reporting period from GET params.

    Returns:
        tuple: (start_date, end_date, period) where period in {'month', 'year', 'custom'}.
    """
    today = date.today()
    period = request.GET.get('period', 'month')

    def _parse(value):
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    if period == 'year':
        start = date(today.year, 1, 1)
        end = date(today.year, 12, 31)
    elif period == 'custom':
        start = _parse(request.GET.get('start'))
        end = _parse(request.GET.get('end'))
        if start is None:
            start = date(today.year, today.month, 1)
        if end is None:
            end = date(today.year, today.month, monthrange(today.year, today.month)[1])
        if end < start:
            start, end = end, start
    else:
        period = 'month'
        start = date(today.year, today.month, 1)
        end = date(today.year, today.month, monthrange(today.year, today.month)[1])

    return start, end, period


@login_required
def tag_overview(request):
    """
    Rentabilität je Tag und aggregiert je Dimension: Einnahmen/Ausgaben/Ergebnis (Brutto),
    geplant vs. tatsächlich getrennt, sowie Stunden/Zeitwert separat (keine Doppelzählung).
    """
    start, end, period = _parse_overview_period(request)
    overview = get_tag_overview(start, end)

    chart_labels = []
    chart_results = []
    for group in overview['groups'].values():
        for row in group['rows']:
            chart_labels.append(row['tag'].name)
            chart_results.append(float(row['result_booked']))

    context = {
        'groups': overview['groups'],
        'untagged': overview['untagged'],
        'grand_totals': overview['grand_totals'],
        'period': period,
        'start': start,
        'end': end,
        'chart_labels': chart_labels,
        'chart_results': chart_results,
    }

    if request.htmx:
        return render(request, 'tags/_tag_overview_content.html', context)

    return render(request, 'tags/tag_overview.html', context)
