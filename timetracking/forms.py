"""Forms for time tracking."""
from django import forms
from django.db.models import Q
from datetime import date
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML
from .models import TimeEntry, Client, MinijobShift, MinijobSettings
from tags.models import Tag


class TimeEntryForm(forms.ModelForm):
    """Form for creating and editing time entries."""

    class Meta:
        model = TimeEntry
        fields = ['client', 'date', 'duration', 'hourly_rate', 'description', 'tags', 'notes']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'duration': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.25', 'min': '0'}),
            'hourly_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'client': 'Kunde',
            'date': 'Datum',
            'duration': 'Dauer (h)',
            'hourly_rate': 'Stundensatz',
            'description': 'Beschreibung',
            'tags': 'Tags',
            'notes': 'Notizen',
        }
        help_texts = {
            'duration': 'z.B. 1.5 für 1h 30min',
            'tags': 'Mehrfachauswahl möglich (Strg/Cmd gedrückt halten), gruppiert nach Dimension',
            'notes': 'Optional',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = False  # Form tag is in the template
        self.helper.layout = Layout(
            'client',
            'date',
            Row(
                Column('duration', css_class='col-md-6'),
                Column('hourly_rate', css_class='col-md-6'),
            ),
            'description',
            'tags',
            'notes',
        )

        # Set required fields
        self.fields['client'].required = True
        self.fields['date'].required = True
        self.fields['duration'].required = True
        self.fields['hourly_rate'].required = True
        self.fields['description'].required = True
        self.fields['tags'].required = False
        self.fields['notes'].required = False

        # Set default date to today if creating new entry
        if not self.instance.pk:
            self.initial['date'] = date.today()

        # Tags: nicht-archivierte Tags + bereits zugeordnete (auch wenn archiviert),
        # als Multi-Select mit optgroups nach Dimension
        assigned_tag_ids = list(self.instance.tags.values_list('pk', flat=True)) if self.instance.pk else []
        tag_queryset = Tag.objects.filter(Q(archived=False) | Q(pk__in=assigned_tag_ids))
        self.fields['tags'].queryset = tag_queryset
        self.fields['tags'].widget = forms.SelectMultiple(attrs={'class': 'form-select', 'size': 6})
        self.fields['tags'].widget.choices = Tag.grouped_choices(tag_queryset)


class ClientForm(forms.ModelForm):
    """Form for creating and editing clients."""

    class Meta:
        model = Client
        fields = ['name', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'name': 'Name',
            'notes': 'Notizen',
        }
        help_texts = {
            'notes': 'Optional',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = False  # Form tag is in the template
        self.helper.layout = Layout(
            'name',
            'notes',
        )

        # Set required fields
        self.fields['name'].required = True
        self.fields['notes'].required = False


class MinijobShiftForm(forms.ModelForm):
    class Meta:
        model = MinijobShift
        fields = ['date', 'start_time', 'end_time', 'break_minutes', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}, format='%H:%M'),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}, format='%H:%M'),
            'break_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '5'}),
            'notes': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['notes'].required = False
        if not self.instance.pk:
            self.initial.setdefault('date', date.today())

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start_time'), cleaned.get('end_time')
        if start and end and start == end:
            raise forms.ValidationError('Beginn und Ende dürfen nicht identisch sein.')
        return cleaned


class MinijobSettingsForm(forms.ModelForm):
    class Meta:
        model = MinijobSettings
        fields = ['employer', 'hourly_rate', 'monthly_limit']
        widgets = {
            'employer': forms.TextInput(attrs={'class': 'form-control'}),
            'hourly_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'monthly_limit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }
