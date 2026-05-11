from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column
from .models import Task


class TaskForm(forms.ModelForm):
    """Form for creating and editing tasks"""

    class Meta:
        model = Task
        fields = ['title', 'description', 'due_date', 'priority', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'title': 'Titel',
            'description': 'Beschreibung',
            'due_date': 'Fälligkeit',
            'priority': 'Priorität',
            'status': 'Status',
        }
        help_texts = {
            'description': 'Optionale Details zur Aufgabe',
            'due_date': 'Optionales Fälligkeitsdatum',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = False  # Form tag is in the template
        self.helper.layout = Layout(
            'title',
            'description',
            Row(
                Column('due_date', css_class='col-md-6'),
                Column('priority', css_class='col-md-6'),
            ),
            'status',
        )

        # Set required fields
        self.fields['title'].required = True
        self.fields['description'].required = False
        self.fields['due_date'].required = False
