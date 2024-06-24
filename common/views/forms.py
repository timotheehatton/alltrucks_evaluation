from django import forms
from users.models import User, Company


class LanguageForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['language']


class CompanyUserForm(forms.ModelForm):
    workshop_first_name = forms.CharField(max_length=150, required=True, label="First name")
    workshop_last_name = forms.CharField(max_length=150, required=True, label="Last name")
    workshop_email = forms.EmailField(required=True, label="Email")
    workshop_ct_number = forms.CharField(max_length=20, required=True, label="CT number")
    
    technician_first_name = forms.CharField(max_length=150, required=True, label="First name")
    technician_last_name = forms.CharField(max_length=150, required=True, label="Last name")
    technician_email = forms.EmailField(required=True, label="Email")
    technician_ct_number = forms.CharField(max_length=20, required=True, label="CT number")

    class Meta:
        model = Company
        fields = ['name', 'city', 'country', 'cu_number']
        labels = {
            'name': 'Company Name',
            'city': 'City',
            'country': 'Country',
            'cu_number': 'CU number'
        }