from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Fieldset, HTML, Div
from .models import AlertConfig


class AlertConfigForm(forms.ModelForm):
    """Form for alert configuration settings"""

    class Meta:
        model = AlertConfig
        fields = [
            'days_before_due',
            'liquidity_threshold',
            'alert_due_enabled',
            'alert_overdue_enabled',
            'alert_liquidity_enabled',
            'smtp_host',
            'smtp_port',
            'smtp_user',
            'smtp_password',
            'smtp_from',
            'smtp_tls',
            'alert_email',
        ]
        widgets = {
            'days_before_due': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'liquidity_threshold': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'alert_due_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'alert_overdue_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'alert_liquidity_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'smtp_host': forms.TextInput(attrs={'class': 'form-control'}),
            'smtp_port': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'smtp_user': forms.TextInput(attrs={'class': 'form-control'}),
            'smtp_password': forms.PasswordInput(attrs={'class': 'form-control'}),
            'smtp_from': forms.EmailInput(attrs={'class': 'form-control'}),
            'smtp_tls': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'alert_email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'days_before_due': 'Vorlaufzeit Fälligkeit (Tage)',
            'liquidity_threshold': 'Liquiditätsschwelle (EUR)',
            'alert_due_enabled': 'Fälligkeits-Alerts aktiviert',
            'alert_overdue_enabled': 'Überfälligkeits-Alerts aktiviert',
            'alert_liquidity_enabled': 'Liquiditäts-Alerts aktiviert',
            'smtp_host': 'SMTP Host',
            'smtp_port': 'SMTP Port',
            'smtp_user': 'SMTP Benutzer',
            'smtp_password': 'SMTP Passwort',
            'smtp_from': 'Absenderadresse',
            'smtp_tls': 'TLS aktivieren',
            'alert_email': 'Empfänger-Adresse',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                'Alert-Schwellenwerte',
                Row(
                    Column('days_before_due', css_class='col-md-6'),
                    Column('liquidity_threshold', css_class='col-md-6'),
                ),
                Row(
                    Column(
                        Div(
                            'alert_due_enabled',
                            css_class='form-check'
                        ),
                        css_class='col-md-4'
                    ),
                    Column(
                        Div(
                            'alert_overdue_enabled',
                            css_class='form-check'
                        ),
                        css_class='col-md-4'
                    ),
                    Column(
                        Div(
                            'alert_liquidity_enabled',
                            css_class='form-check'
                        ),
                        css_class='col-md-4'
                    ),
                ),
            ),
            Fieldset(
                'E-Mail-Benachrichtigung',
                Row(
                    Column('smtp_host', css_class='col-md-8'),
                    Column('smtp_port', css_class='col-md-4'),
                ),
                Row(
                    Column('smtp_user', css_class='col-md-6'),
                    Column('smtp_password', css_class='col-md-6'),
                ),
                Row(
                    Column('smtp_from', css_class='col-md-6'),
                    Column('alert_email', css_class='col-md-6'),
                ),
                Div(
                    'smtp_tls',
                    css_class='form-check'
                ),
            ),
        )

        # Set required fields
        self.fields['days_before_due'].required = True
        self.fields['liquidity_threshold'].required = True
