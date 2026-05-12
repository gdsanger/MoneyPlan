from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, HTML, Div
from .models import Booking, Category, RecurringSeries, Liability, Asset
from datetime import date


ISO_DATE_FORMAT = '%Y-%m-%d'


class QuickBookingForm(forms.ModelForm):
    """Compact form for quick booking entry on dashboard"""

    class Meta:
        model = Booking
        fields = ['date', 'description', 'amount', 'category', 'status']
        widgets = {
            'date': forms.DateInput(format=ISO_DATE_FORMAT, attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'z.B. Einkauf Supermarkt'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'date': 'Datum',
            'description': 'Beschreibung',
            'amount': 'Betrag',
            'category': 'Kategorie',
            'status': 'Status',
        }
        help_texts = {
            'amount': 'Positiv = Einnahme, Negativ = Ausgabe',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = False  # We'll add form tag in template

        # Compact layout: all fields in a single row on desktop
        self.helper.layout = Layout(
            Row(
                Column('date', css_class='col-md-2 col-12'),
                Column('description', css_class='col-md-3 col-12'),
                Column('amount', css_class='col-md-2 col-12'),
                Column('category', css_class='col-md-3 col-12'),
                Column('status', css_class='col-md-2 col-12'),
            ),
        )

        # Make all fields required
        self.fields['date'].required = True
        self.fields['description'].required = True
        self.fields['amount'].required = True
        self.fields['category'].required = True
        self.fields['status'].required = True

        # Set default date to today
        if not self.instance.pk:
            self.fields['date'].initial = date.today()
            self.fields['status'].initial = 'booked'  # Default to "Gebucht"


class BookingForm(forms.ModelForm):
    """Form for creating and editing bookings"""

    class Meta:
        model = Booking
        fields = ['date', 'description', 'amount', 'category', 'status', 'liability', 'notes']
        widgets = {
            'date': forms.DateInput(format=ISO_DATE_FORMAT, attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'liability': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'date': 'Datum',
            'description': 'Beschreibung',
            'amount': 'Betrag',
            'category': 'Kategorie',
            'status': 'Status',
            'liability': 'Verbindlichkeit',
            'notes': 'Notizen',
        }
        help_texts = {
            'amount': 'Positiv = Einnahme, Negativ = Ausgabe',
            'liability': 'Ordne diese Ausgabe einer Verbindlichkeit zu (nur für Ausgaben)',
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
            'liability',
            'notes',
        )

        # Make fields required
        self.fields['date'].required = True
        self.fields['description'].required = True
        self.fields['amount'].required = True
        self.fields['category'].required = True
        self.fields['status'].required = True
        self.fields['liability'].required = False
        self.fields['notes'].required = False

        # Filter liability to only show open liabilities
        self.fields['liability'].queryset = Liability.objects.all()
        self.fields['liability'].empty_label = "Keine Zuordnung"


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


class CategoryForm(forms.ModelForm):
    """Form for creating and editing categories"""

    class Meta:
        model = Category
        fields = ['name', 'icon', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'icon': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. bi-house',
                'id': 'id_icon',
            }),
            'color': forms.TextInput(attrs={
                'type': 'color',
                'class': 'form-control form-control-color',
                'id': 'id_color',
            }),
        }
        labels = {
            'name': 'Name',
            'icon': 'Bootstrap Icon',
            'color': 'Farbe',
        }
        help_texts = {
            'icon': 'Bootstrap Icon Klasse (z.B. bi-house, bi-cart)',
            'color': 'Farbe als Hex-Wert',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'name',
            Div(
                'icon',
                HTML('''
                    <div class="mt-2 mb-3">
                        <label class="form-label">Vorschau:</label>
                        <div id="icon-preview" class="fs-1">
                            <i class="bi {% if form.icon.value %}bi-{{ form.icon.value }}{% else %}bi-question-circle{% endif %}"></i>
                        </div>
                    </div>
                '''),
            ),
            Div(
                'color',
                HTML('''
                    <div class="mt-2 mb-3">
                        <label class="form-label">Hex-Wert:</label>
                        <input type="text" id="hex-value-display" class="form-control" readonly value="{{ form.color.value|default:'#6c757d' }}">
                    </div>
                '''),
            ),
        )
        self.fields['name'].required = True
        self.fields['icon'].required = False
        self.fields['color'].required = True

    def clean_icon(self):
        icon = self.cleaned_data.get('icon', '').strip()
        if icon and not icon.startswith('bi-'):
            icon = 'bi-' + icon
        return icon


class RecurringSeriesForm(forms.ModelForm):
    """Form for creating recurring series"""

    class Meta:
        model = RecurringSeries
        fields = ['description', 'amount', 'interval', 'start_date', 'end_date', 'category', 'notes']
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'interval': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(format=ISO_DATE_FORMAT, attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(format=ISO_DATE_FORMAT, attrs={'type': 'date', 'class': 'form-control'}),
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
        self.fields['description'].required = True
        self.fields['amount'].required = True
        self.fields['interval'].required = True
        self.fields['start_date'].required = True
        self.fields['end_date'].required = False
        self.fields['category'].required = True
        self.fields['notes'].required = False


class LiabilityForm(forms.ModelForm):
    """Form for creating and editing liabilities"""

    class Meta:
        model = Liability
        fields = ['name', 'description', 'initial_amount', 'start_date', 'due_date', 'category', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'initial_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'start_date': forms.DateInput(format=ISO_DATE_FORMAT, attrs={'type': 'date', 'class': 'form-control'}),
            'due_date': forms.DateInput(format=ISO_DATE_FORMAT, attrs={'type': 'date', 'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'name': 'Name',
            'description': 'Beschreibung',
            'initial_amount': 'Vortrag (€)',
            'start_date': 'Startdatum',
            'due_date': 'Fälligkeit',
            'category': 'Kategorie',
            'notes': 'Notizen',
        }
        help_texts = {
            'initial_amount': 'Aktueller Schuldenstand bei Erfassung',
            'description': 'Optionale Beschreibung der Verbindlichkeit',
            'due_date': 'Optional - Fälligkeitsdatum',
            'notes': 'Optionale Notizen',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'name',
            'description',
            Row(
                Column('initial_amount', css_class='col-md-6'),
                Column('category', css_class='col-md-6'),
            ),
            Row(
                Column('start_date', css_class='col-md-6'),
                Column('due_date', css_class='col-md-6'),
            ),
            'notes',
        )

        # Make fields required
        self.fields['name'].required = True
        self.fields['description'].required = False
        self.fields['initial_amount'].required = True
        self.fields['start_date'].required = True
        self.fields['due_date'].required = False
        self.fields['category'].required = True
        self.fields['notes'].required = False


class AssetForm(forms.ModelForm):
    """Form for creating and editing assets"""

    class Meta:
        model = Asset
        fields = ['name', 'category', 'description', 'purchase_date', 'purchase_price', 'current_value', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'purchase_date': forms.DateInput(format=ISO_DATE_FORMAT, attrs={'type': 'date', 'class': 'form-control'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'current_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'name': 'Name',
            'category': 'Kategorie',
            'description': 'Beschreibung',
            'purchase_date': 'Kaufdatum',
            'purchase_price': 'Kaufpreis (€)',
            'current_value': 'Aktueller Wert (€)',
            'notes': 'Notizen',
        }
        help_texts = {
            'purchase_price': 'Ursprünglicher Kaufpreis für Wertentwicklung',
            'current_value': 'Geschätzter aktueller Marktwert',
            'description': 'Optionale Beschreibung des Vermögensgegenstandes',
            'purchase_date': 'Optional - Kaufdatum',
            'notes': 'Optionale Notizen',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = False  # We'll add form tag in template
        self.helper.layout = Layout(
            'name',
            'category',
            'description',
            Row(
                Column('purchase_date', css_class='col-md-6'),
                Column('purchase_price', css_class='col-md-6'),
            ),
            'current_value',
            'notes',
        )

        # Set required fields
        self.fields['name'].required = True
        self.fields['category'].required = True
        self.fields['description'].required = False
        self.fields['purchase_date'].required = False
        self.fields['purchase_price'].required = False
        self.fields['current_value'].required = True
        self.fields['notes'].required = False


class AssetQuickUpdateForm(forms.ModelForm):
    """Quick form for updating only the current value of an asset"""

    class Meta:
        model = Asset
        fields = ['current_value']
        widgets = {
            'current_value': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm',
                'step': '0.01',
                'placeholder': 'Neuer Wert'
            }),
        }
        labels = {
            'current_value': '',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['current_value'].required = True


