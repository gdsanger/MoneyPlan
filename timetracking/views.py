"""Views for time tracking."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.urls import reverse
from datetime import date
from .models import TimeEntry, Client
from .forms import TimeEntryForm, ClientForm
from .services import get_unbilled_total, get_forecast_entry


@login_required
def time_entry_list(request):
    """List all time entries with filters."""
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    client_filter = request.GET.get('client', 'all')
    month_filter = request.GET.get('month', 'all')

    # Start with all entries
    entries = TimeEntry.objects.select_related('client').all()

    # Apply filters
    if status_filter == 'unbilled':
        entries = entries.filter(billed=False)
    elif status_filter == 'billed':
        entries = entries.filter(billed=True)

    if client_filter != 'all':
        entries = entries.filter(client_id=client_filter)

    if month_filter != 'all':
        # month_filter format: "2026-05"
        try:
            year, month = month_filter.split('-')
            entries = entries.filter(date__year=int(year), date__month=int(month))
        except (ValueError, AttributeError):
            pass

    # Calculate summary
    unbilled_total = get_unbilled_total()
    forecast_entry = get_forecast_entry()

    # Calculate unbilled hours
    unbilled_entries = TimeEntry.objects.filter(billed=False)
    unbilled_hours = sum(e.duration for e in unbilled_entries)

    # Get all clients for filter dropdown
    clients = Client.objects.all()

    context = {
        'entries': entries,
        'status_filter': status_filter,
        'client_filter': client_filter,
        'month_filter': month_filter,
        'clients': clients,
        'unbilled_total': unbilled_total,
        'unbilled_hours': unbilled_hours,
        'forecast_entry': forecast_entry,
    }

    # If HTMX request, return only the list partial
    if request.htmx:
        return render(request, 'timetracking/_list.html', context)

    return render(request, 'timetracking/list.html', context)


@login_required
def time_entry_create(request):
    """Create a new time entry."""
    if request.method == 'POST':
        form = TimeEntryForm(request.POST)
        if form.is_valid():
            entry = form.save()

            # If HTMX request, redirect to list
            if request.htmx:
                response = HttpResponse(status=204)
                response['HX-Redirect'] = reverse('timetracking:list')
                return response

            return redirect('timetracking:list')
    else:
        form = TimeEntryForm()

    context = {
        'form': form,
        'is_create': True,
    }

    # If HTMX request, return only the form partial
    if request.htmx:
        return render(request, 'timetracking/_form.html', context)

    return render(request, 'timetracking/form.html', context)


@login_required
def time_entry_edit(request, entry_id):
    """Edit a time entry."""
    entry = get_object_or_404(TimeEntry, pk=entry_id)

    if request.method == 'POST':
        form = TimeEntryForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()

            # If HTMX request, redirect to list
            if request.htmx:
                response = HttpResponse(status=204)
                response['HX-Redirect'] = reverse('timetracking:list')
                return response

            return redirect('timetracking:list')
    else:
        form = TimeEntryForm(instance=entry)

    context = {
        'form': form,
        'entry': entry,
        'is_create': False,
    }

    # If HTMX request, return only the form partial
    if request.htmx:
        return render(request, 'timetracking/_form.html', context)

    return render(request, 'timetracking/form.html', context)


@login_required
def time_entry_delete(request, entry_id):
    """Delete a time entry."""
    entry = get_object_or_404(TimeEntry, pk=entry_id)

    if request.method == 'POST':
        entry.delete()

        # If HTMX request, redirect to list
        if request.htmx:
            response = HttpResponse(status=204)
            response['HX-Redirect'] = reverse('timetracking:list')
            return response

        return redirect('timetracking:list')

    # For GET, should not happen but redirect to list
    return redirect('timetracking:list')


@login_required
def time_entry_toggle_billed(request, entry_id):
    """Toggle billed status of a time entry (HTMX only)."""
    entry = get_object_or_404(TimeEntry, pk=entry_id)

    if request.method == 'POST':
        entry.billed = not entry.billed
        entry.save()

        # Return updated row
        context = {
            'entry': entry,
        }
        return render(request, 'timetracking/_row.html', context)

    return HttpResponse(status=400)


@login_required
def client_list(request):
    """List all clients."""
    clients = Client.objects.all()

    context = {
        'clients': clients,
    }

    return render(request, 'timetracking/client_list.html', context)


@login_required
def client_create(request):
    """Create a new client."""
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()

            # If HTMX request, redirect to client list
            if request.htmx:
                response = HttpResponse(status=204)
                response['HX-Redirect'] = reverse('timetracking:client_list')
                return response

            return redirect('timetracking:client_list')
    else:
        form = ClientForm()

    context = {
        'form': form,
        'is_create': True,
    }

    # If HTMX request, return only the form partial
    if request.htmx:
        return render(request, 'timetracking/_client_form.html', context)

    return render(request, 'timetracking/client_form.html', context)


@login_required
def client_edit(request, client_id):
    """Edit a client."""
    client = get_object_or_404(Client, pk=client_id)

    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()

            # If HTMX request, redirect to client list
            if request.htmx:
                response = HttpResponse(status=204)
                response['HX-Redirect'] = reverse('timetracking:client_list')
                return response

            return redirect('timetracking:client_list')
    else:
        form = ClientForm(instance=client)

    context = {
        'form': form,
        'client': client,
        'is_create': False,
    }

    # If HTMX request, return only the form partial
    if request.htmx:
        return render(request, 'timetracking/_client_form.html', context)

    return render(request, 'timetracking/client_form.html', context)


@login_required
def client_delete(request, client_id):
    """Delete a client."""
    client = get_object_or_404(Client, pk=client_id)

    if request.method == 'POST':
        try:
            client.delete()
        except Exception as e:
            # If client has entries, cannot delete due to PROTECT
            # Could add error message here
            pass

        # If HTMX request, redirect to client list
        if request.htmx:
            response = HttpResponse(status=204)
            response['HX-Redirect'] = reverse('timetracking:client_list')
            return response

        return redirect('timetracking:client_list')

    # For GET, should not happen but redirect to list
    return redirect('timetracking:client_list')

