from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, HTML
from .models import Booking, Category, RecurringSeries


class BookingForm(forms.ModelForm):
    """Form for creating and editing bookings"""

    class Meta:
        model = Booking
        fields = ['date', 'description', 'amount', 'category', 'status', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'date': 'Datum',
            'description': 'Beschreibung',
            'amount': 'Betrag',
            'category': 'Kategorie',
            'status': 'Status',
            'notes': 'Notizen',
        }
        help_texts = {
            'amount': 'Positiv = Einnahme, Negativ = Ausgabe',
            'notes': 'Optionale Notizen zur Buchung',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('date', css_class='col-md-6'),
                Column('status', css_class='col-md-6'),
            ),
            'description',
            Row(
                Column('amount', css_class='col-md-6'),
                Column('category', css_class='col-md-6'),
            ),
            'notes',
        )

        # Make fields required
        self.fields['date'].required = True
        self.fields['description'].required = True
        self.fields['amount'].required = True
        self.fields['category'].required = True
        self.fields['status'].required = True
        self.fields['notes'].required = False


class BookingFilterForm(forms.Form):
    """Form for filtering bookings"""

    STATUS_CHOICES = [
        ('', 'Alle'),
        ('planned', 'Geplant'),
        ('booked', 'Gebucht'),
    ]

    TYPE_CHOICES = [
        ('', 'Alle'),
        ('income', 'Einnahmen'),
        ('expense', 'Ausgaben'),
    ]

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        label='Status',
        widget=forms.Select(attrs={'class': 'form-select', 'hx-get': '', 'hx-trigger': 'change', 'hx-target': '#booking-list-container', 'hx-swap': 'innerHTML'})
    )

    type = forms.ChoiceField(
        choices=TYPE_CHOICES,
        required=False,
        label='Typ',
        widget=forms.Select(attrs={'class': 'form-select', 'hx-get': '', 'hx-trigger': 'change', 'hx-target': '#booking-list-container', 'hx-swap': 'innerHTML'})
    )

    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        label='Kategorie',
        empty_label='Alle',
        widget=forms.Select(attrs={'class': 'form-select', 'hx-get': '', 'hx-trigger': 'change', 'hx-target': '#booking-list-container', 'hx-swap': 'innerHTML'})
    )

    month = forms.DateField(
        required=False,
        label='Monat',
        widget=forms.DateInput(attrs={'type': 'month', 'class': 'form-control', 'hx-get': '', 'hx-trigger': 'change', 'hx-target': '#booking-list-container', 'hx-swap': 'innerHTML'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the hx-get attribute to the current URL
        for field_name in ['status', 'type', 'category', 'month']:
            if field_name in self.fields:
                # The actual URL will be set in the template
                pass


class RecurringSeriesForm(forms.ModelForm):
    """Form for creating recurring series"""

    class Meta:
        model = RecurringSeries
        fields = ['description', 'amount', 'interval', 'start_date', 'end_date', 'category', 'notes']
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'interval': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'description': 'Beschreibung',
            'amount': 'Betrag',
            'interval': 'Intervall',
            'start_date': 'Startdatum',
            'end_date': 'Enddatum',
            'category': 'Kategorie',
            'notes': 'Notizen',
        }
        help_texts = {
            'amount': 'Positiv = Einnahme, Negativ = Ausgabe',
            'end_date': 'Optional - leer lassen für automatische Vorschau über 2 Jahre',
            'notes': 'Optionale Notizen zur Serie',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'description',
            Row(
                Column('amount', css_class='col-md-6'),
                Column('category', css_class='col-md-6'),
            ),
            Row(
                Column('interval', css_class='col-md-6'),
                Column('start_date', css_class='col-md-6'),
            ),
            'end_date',
            'notes',
        )

        # Make fields required
        self.fields['description'].required = True
        self.fields['amount'].required = True
        self.fields['interval'].required = True
        self.fields['start_date'].required = True
        self.fields['end_date'].required = False
        self.fields['category'].required = True
        self.fields['notes'].required = False
