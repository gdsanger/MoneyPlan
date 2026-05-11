from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from datetime import date, timedelta
from .models import Task
from .forms import TaskForm


@login_required
def task_list(request):
    """Liste aller Aufgaben mit Filtern"""
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    priority_filter = request.GET.get('priority', 'all')
    due_filter = request.GET.get('due', 'all')

    # Start with all tasks
    tasks = Task.objects.all()

    # Apply filters
    if status_filter == 'open':
        tasks = tasks.filter(status='open')
    elif status_filter == 'done':
        tasks = tasks.filter(status='done')

    if priority_filter != 'all':
        tasks = tasks.filter(priority=priority_filter)

    today = date.today()
    if due_filter == 'today':
        tasks = tasks.filter(due_date=today)
    elif due_filter == 'week':
        week_end = today + timedelta(days=7)
        tasks = tasks.filter(due_date__gte=today, due_date__lte=week_end)
    elif due_filter == 'overdue':
        tasks = tasks.filter(due_date__lt=today, status='open')

    context = {
        'tasks': tasks,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'due_filter': due_filter,
        'today': today,
    }

    # If HTMX request, return only the list partial
    if request.htmx:
        return render(request, 'tasks/_list.html', context)

    return render(request, 'tasks/list.html', context)


@login_required
def task_create(request):
    """Erstelle eine neue Aufgabe"""
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save()

            # If HTMX request, redirect to list
            if request.htmx:
                response = HttpResponse(status=204)
                response['HX-Redirect'] = '/aufgaben/'
                return response

            return redirect('tasks:list')
    else:
        form = TaskForm()

    context = {
        'form': form,
        'task': None,
    }

    # If HTMX request, return only the form partial
    if request.htmx:
        return render(request, 'tasks/_form.html', context)

    return render(request, 'tasks/form.html', context)


@login_required
def task_edit(request, task_id):
    """Bearbeite eine Aufgabe"""
    task = get_object_or_404(Task, pk=task_id)

    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            task = form.save()

            # If HTMX request, redirect to list
            if request.htmx:
                response = HttpResponse(status=204)
                response['HX-Redirect'] = '/aufgaben/'
                return response

            return redirect('tasks:list')
    else:
        form = TaskForm(instance=task)

    context = {
        'form': form,
        'task': task,
    }

    # If HTMX request, return only the form partial
    if request.htmx:
        return render(request, 'tasks/_form.html', context)

    return render(request, 'tasks/form.html', context)


@login_required
def task_delete(request, task_id):
    """Lösche eine Aufgabe"""
    task = get_object_or_404(Task, pk=task_id)

    if request.method == 'POST':
        task.delete()

        # If HTMX request, return empty response
        if request.htmx:
            return HttpResponse(status=204)

        return redirect('tasks:list')

    return HttpResponse(status=405)


@login_required
def task_toggle_done(request, task_id):
    """Toggle Aufgabe zwischen Offen und Erledigt (HTMX only)"""
    if request.method != 'POST':
        return HttpResponse(status=405)

    task = get_object_or_404(Task, pk=task_id)

    # Toggle status
    if task.status == 'open':
        task.status = 'done'
    else:
        task.status = 'open'
    task.save()

    # Return updated row
    context = {
        'task': task,
        'today': date.today(),
    }
    return render(request, 'tasks/_row.html', context)
