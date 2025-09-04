
from django import forms
from .models import EconomicIndicator

class EconomicIndicatorForm(forms.ModelForm):
    class Meta:
        model = EconomicIndicator
        fields = [
            'year', 'gdp_zar_bn', 'inflation_rate',
            'gdp_yoy_change', 'inflation_yoy_change', 'era',
        ]
        widgets = {
            'era': forms.Select(choices=[('Apartheid','Apartheid'), ('Post-Apartheid','Post-Apartheid')])
        }



