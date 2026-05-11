from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def booking_list(request):
    """Liste aller Buchungen"""
    return render(request, 'bookings/booking_list.html')


@login_required
def category_list(request):
    """Liste aller Kategorien"""
    return render(request, 'bookings/category_list.html')


@login_required
def series_list(request):
    """Liste aller wiederkehrenden Serien"""
    return render(request, 'bookings/series_list.html')
