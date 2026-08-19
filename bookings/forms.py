from django import forms
from django.db.models import Q
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, HTML, Div
from .models import Booking, Category, RecurringSeries, Liability, Asset, Account, AccountBalance
from tags.models import Tag
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
        fields = ['date', 'description', 'amount', 'category', 'status', 'liability', 'tags', 'notes']
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
            'tags': 'Tags',
            'notes': 'Notizen',
        }
        help_texts = {
            'amount': 'Positiv = Einnahme, Negativ = Ausgabe',
            'liability': 'Ordne diese Ausgabe einer Verbindlichkeit zu (nur für Ausgaben)',
            'tags': 'Mehrfachauswahl möglich (Strg/Cmd gedrückt halten), gruppiert nach Dimension',
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
            'tags',
            'notes',
        )

        # Make fields required
        self.fields['date'].required = True
        self.fields['description'].required = True
        self.fields['amount'].required = True
        self.fields['category'].required = True
        self.fields['status'].required = True
        self.fields['liability'].required = False
        self.fields['tags'].required = False
        self.fields['notes'].required = False

        # Filter liability to only show open liabilities
        self.fields['liability'].queryset = Liability.objects.all()
        self.fields['liability'].empty_label = "Keine Zuordnung"

        # Tags: nicht-archivierte Tags + bereits zugeordnete (auch wenn archiviert),
        # als Multi-Select mit optgroups nach Dimension
        assigned_tag_ids = list(self.instance.tags.values_list('pk', flat=True)) if self.instance.pk else []
        tag_queryset = Tag.objects.filter(Q(archived=False) | Q(pk__in=assigned_tag_ids))
        self.fields['tags'].queryset = tag_queryset
        self.fields['tags'].widget = forms.SelectMultiple(attrs={'class': 'form-select', 'size': 6})
        self.fields['tags'].widget.choices = Tag.grouped_choices(tag_queryset)


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

    tag = forms.ModelChoiceField(
        queryset=Tag.objects.filter(archived=False),
        required=False,
        label='Tag',
        empty_label='Alle',
        widget=forms.Select(attrs={'class': 'form-select', 'hx-get': '', 'hx-trigger': 'change', 'hx-target': '#booking-list-container', 'hx-swap': 'innerHTML'})
    )

    tag_kind = forms.ChoiceField(
        choices=[('', 'Alle')] + Tag.KIND_CHOICES,
        required=False,
        label='Dimension',
        widget=forms.Select(attrs={'class': 'form-select', 'hx-get': '', 'hx-trigger': 'change', 'hx-target': '#booking-list-container', 'hx-swap': 'innerHTML'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tag'].widget.choices = [('', 'Alle')] + Tag.grouped_choices()


class MonthFilterForm(forms.Form):
    """Form for filtering bookings within the monthly view (date, amount, category, description)"""

    TYPE_CHOICES = [
        ('', 'Alle'),
        ('income', 'Einnahme'),
        ('expense', 'Ausgabe'),
    ]

    date_from = forms.DateField(
        required=False,
        label='Datum von',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'hx-trigger': 'change'})
    )

    date_to = forms.DateField(
        required=False,
        label='Datum bis',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'hx-trigger': 'change'})
    )

    amount_min = forms.DecimalField(
        required=False,
        label='Betrag von',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'min', 'hx-trigger': 'change'})
    )

    amount_max = forms.DecimalField(
        required=False,
        label='Betrag bis',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'max', 'hx-trigger': 'change'})
    )

    type = forms.ChoiceField(
        choices=TYPE_CHOICES,
        required=False,
        label='Typ',
        widget=forms.Select(attrs={'class': 'form-select', 'hx-trigger': 'change'})
    )

    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        label='Kategorie',
        empty_label='Alle',
        widget=forms.Select(attrs={'class': 'form-select', 'hx-trigger': 'change'})
    )

    description = forms.CharField(
        required=False,
        label='Beschreibung',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Suche in Beschreibung...',
            'hx-trigger': 'keyup changed delay:500ms, change',
        })
    )

    def __init__(self, *args, month_url=None, **kwargs):
        super().__init__(*args, **kwargs)
        if month_url:
            for field in self.fields.values():
                field.widget.attrs.update({
                    'hx-get': month_url,
                    'hx-target': '#month-content',
                    'hx-swap': 'innerHTML',
                    'hx-include': '#month-filter-form',
                })


class CategoryForm(forms.ModelForm):
    """Form for creating and editing categories"""

    class Meta:
        model = Category
        fields = ['name', 'category_type', 'description', 'icon', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'z.B. Regelmäßige Wohnkosten inkl. Nebenkosten',
            }),
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
            'category_type': 'Typ',
            'description': 'Beschreibung',
            'icon': 'Bootstrap Icon',
            'color': 'Farbe',
        }
        help_texts = {
            'category_type': 'Einnahmen und Ausgaben fließen in Statistiken ein, Neutral nicht.',
            'description': 'Wird dem KI-Finanzassistenten mitgegeben, damit er die Kategorie korrekt einordnet.',
            'icon': 'Bootstrap Icon Klasse (z.B. bi-house, bi-cart)',
            'color': 'Farbe als Hex-Wert',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'name',
            'category_type',
            'description',
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
        self.fields['category_type'].required = True
        self.fields['description'].required = False
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


class SeriesAmountChangeForm(forms.Form):
    """Form for changing a series' amount from a given cutoff date onward"""

    new_amount = forms.DecimalField(
        label='Neuer Betrag',
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        help_text='Positiv = Einnahme, Negativ = Ausgabe',
    )
    valid_from = forms.DateField(
        label='Gültig ab',
        widget=forms.DateInput(format=ISO_DATE_FORMAT, attrs={'type': 'date', 'class': 'form-control'}),
        help_text='Ändert nur geplante, noch nicht gebuchte Buchungen ab diesem Datum',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column('new_amount', css_class='col-md-6'),
                Column('valid_from', css_class='col-md-6'),
            ),
        )


class SeriesExtendForm(forms.Form):
    """Form for extending a series' end date and generating missing bookings up to it"""

    new_end_date = forms.DateField(
        label='Verlängern bis',
        widget=forms.DateInput(format=ISO_DATE_FORMAT, attrs={'type': 'date', 'class': 'form-control'}),
        help_text='Fehlende Buchungen bis zu diesem Datum werden mit dem aktuellen Betrag angelegt.',
    )

    def __init__(self, *args, series=None, **kwargs):
        self.series = series
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout('new_end_date')

    def clean_new_end_date(self):
        new_end_date = self.cleaned_data['new_end_date']
        if self.series and self.series.end_date and new_end_date <= self.series.end_date:
            raise forms.ValidationError(
                'Das neue Datum muss nach dem aktuellen Enddatum der Serie liegen.'
            )
        return new_end_date


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


class ReconciliationForm(forms.Form):
    """Ist-Gesamtstand erfassen und Kategorie für die Ausgleichsbuchung wählen"""

    actual_balance = forms.DecimalField(
        max_digits=10, decimal_places=2,
        label='Ist-Gesamtstand',
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'step': '0.01',
            'inputmode': 'decimal',
            'placeholder': '0.00',
            'autocomplete': 'off',
        }),
        help_text='Summe der realen Kontostände (Girokonto, Tagesgeld, Bargeld, ...).',
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        label='Kategorie der Ausgleichsbuchung',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, calc_url=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].required = True

        if calc_url:
            self.fields['actual_balance'].widget.attrs.update({
                'hx-get': calc_url,
                'hx-trigger': 'input changed delay:400ms, change',
                'hx-target': '#reconciliation-result',
                'hx-include': '#reconciliation-form',
                'hx-swap': 'innerHTML',
            })


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




class AccountForm(forms.ModelForm):
    """Konto anlegen/bearbeiten (ohne Bezug zu Buchungen)."""

    class Meta:
        model = Account
        fields = ['name', 'account_type', 'sort_order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'z. B. Girokonto Sparkasse'}),
            'account_type': forms.Select(attrs={'class': 'form-select'}),
            'sort_order': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Name',
            'account_type': 'Typ',
            'sort_order': 'Sortierung',
            'is_active': 'Aktiv',
        }
        help_texts = {
            'sort_order': 'Kleinere Werte werden zuerst angezeigt.',
            'is_active': 'Deaktivierte Konten zählen nicht zur Gesamtsumme.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.fields['name'].required = True


class AccountBalanceForm(forms.ModelForm):
    """Einzelnen Kontostand-Eintrag erfassen/korrigieren."""

    class Meta:
        model = AccountBalance
        fields = ['account', 'date', 'balance', 'note']
        widgets = {
            'account': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(format=ISO_DATE_FORMAT, attrs={'type': 'date', 'class': 'form-control'}),
            'balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'inputmode': 'decimal'}),
            'note': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optionale Notiz'}),
        }
        labels = {
            'account': 'Konto',
            'date': 'Datum',
            'balance': 'Kontostand (€)',
            'note': 'Notiz',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date'].input_formats = [ISO_DATE_FORMAT]
        self.fields['account'].queryset = Account.objects.filter(is_active=True)
        self.helper = FormHelper()
        self.helper.form_tag = False

    def validate_unique(self):
        """Freundliche Fehlermeldung bei doppeltem (Konto, Datum)."""
        try:
            super().validate_unique()
        except forms.ValidationError as e:
            self.add_error(None, 'Für dieses Konto existiert bereits ein Stand an diesem Datum. Bitte den vorhandenen Eintrag bearbeiten.')
