from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit


class AttachmentUploadForm(forms.Form):
    """Form for uploading file attachments"""
    file = forms.FileField(
        label='Datei auswählen',
        help_text='Max. 10 MB. Erlaubte Dateitypen: PDF, Bilder, Office-Dokumente, CSV, Text',
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = False
        self.helper.layout = Layout('file')
