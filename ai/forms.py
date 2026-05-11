"""Forms for AI configuration."""
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, HTML, Div, Field
from crispy_forms.bootstrap import FormActions
from .models import AIConfig


class AIConfigForm(forms.ModelForm):
    """Form for AI configuration settings."""

    class Meta:
        model = AIConfig
        fields = [
            'enabled',
            'provider',
            'openai_api_key',
            'openai_model',
            'anthropic_api_key',
            'anthropic_model',
            'max_tokens',
        ]
        widgets = {
            'openai_api_key': forms.PasswordInput(render_value=True),
            'anthropic_api_key': forms.PasswordInput(render_value=True),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                'KI-Belegerkennung',
                Field('enabled', wrapper_class='mb-3'),
                Field('provider', wrapper_class='mb-3'),
            ),
            Fieldset(
                'OpenAI',
                Field('openai_api_key', wrapper_class='mb-3'),
                Field('openai_model', wrapper_class='mb-3'),
                css_class='mt-3'
            ),
            Fieldset(
                'Anthropic',
                Field('anthropic_api_key', wrapper_class='mb-3'),
                Field('anthropic_model', wrapper_class='mb-3'),
                css_class='mt-3'
            ),
            Fieldset(
                'Erweiterte Einstellungen',
                Field('max_tokens', wrapper_class='mb-3'),
                css_class='mt-3'
            ),
            FormActions(
                Submit('save', 'Speichern', css_class='btn btn-primary'),
                css_class='mt-3'
            )
        )

        # Add help text
        self.fields['enabled'].help_text = 'Aktiviere KI-basierte Belegerkennung'
        self.fields['provider'].help_text = 'Aktiver AI-Provider (OpenAI oder Anthropic)'
        self.fields['openai_api_key'].help_text = 'API-Schlüssel von OpenAI (https://platform.openai.com/)'
        self.fields['openai_model'].help_text = 'OpenAI-Modell für Vision-Aufgaben'
        self.fields['anthropic_api_key'].help_text = 'API-Schlüssel von Anthropic (https://console.anthropic.com/)'
        self.fields['anthropic_model'].help_text = 'Anthropic-Modell für Vision-Aufgaben'
        self.fields['max_tokens'].help_text = 'Maximale Token-Anzahl für Antworten'
