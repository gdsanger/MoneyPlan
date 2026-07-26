from django import forms
from .models import Tag


class TagForm(forms.ModelForm):
    """Form for creating and editing tags"""

    class Meta:
        model = Tag
        fields = ['name', 'kind', 'description', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'kind': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'z.B. Projekt "Website-Relaunch" für Kunde XY',
            }),
            'color': forms.TextInput(attrs={
                'type': 'color',
                'class': 'form-control form-control-color',
                'id': 'id_color',
            }),
        }
        labels = {
            'name': 'Name',
            'kind': 'Dimension',
            'description': 'Beschreibung',
            'color': 'Farbe',
        }
        help_texts = {
            'kind': 'Gruppierung des Tags, z.B. für Charts und Filter.',
            'color': 'Farbe als Hex-Wert',
        }

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        kind = cleaned_data.get('kind')

        if name and kind:
            existing = Tag.objects.filter(kind=kind, name__iexact=name)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError(
                    f'Ein Tag mit dem Namen "{name}" existiert bereits in der Dimension "{dict(Tag.KIND_CHOICES).get(kind, kind)}".'
                )

        return cleaned_data
