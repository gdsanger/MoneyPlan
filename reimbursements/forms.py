from django import forms
from .models import ExpenseClaim, ReimbursementConfig


class ExpenseClaimForm(forms.ModelForm):
    class Meta:
        model = ExpenseClaim
        fields = ['date', 'description', 'amount', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ReimbursementConfigForm(forms.ModelForm):
    class Meta:
        model = ReimbursementConfig
        fields = [
            'employee_name',
            'bank_name',
            'iban',
            'bic',
            'expense_purpose',
            'place',
            'recipient_email',
            'logo',
            'signature_image',
        ]
        widgets = {
            'employee_name': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'iban': forms.TextInput(attrs={'class': 'form-control'}),
            'bic': forms.TextInput(attrs={'class': 'form-control'}),
            'expense_purpose': forms.TextInput(attrs={'class': 'form-control'}),
            'place': forms.TextInput(attrs={'class': 'form-control'}),
            'recipient_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'signature_image': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
