from django import forms
from django.forms import DateInput
from django.forms import inlineformset_factory
from django.forms import BaseInlineFormSet
from django.contrib.auth import get_user_model

from allauth.account.forms import SignupForm

from .models import Production, ProductionTask, Unit, Task

class BaseProductionTaskFormSet(BaseInlineFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        form.fields['task_time'].widget = forms.TextInput(attrs={'type': 'range', 'min': 0, 'max': 10, 'step': 0.25, 'class': 'range-slider'})

ProductionTaskFormSet = inlineformset_factory(
    Production,
    ProductionTask,
    fields=('task', 'unit', 'task_time'),
    extra=9,
    min_num=1,
    can_delete=True,
    formset=BaseProductionTaskFormSet,
)

class ProductionForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(),
        widget=forms.Select,
        required=True
    )

    class Meta:
        model = Production
        fields = ['user', 'entry_date', 'notes']
        widgets = {
            'entry_date': DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        formset = kwargs.pop('formset', None)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.formset = formset
        if user:
            self.fields['user'].queryset = get_user_model().objects.filter(pk=user.pk)

    def is_valid(self):
        form_valid = super().is_valid()
        formset_valid = self.formset.is_valid() if self.formset else True
        return form_valid and formset_valid

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
        if self.formset:
            self.formset.instance = instance
            self.formset.save(commit=commit)
            self.formset.save_m2m()
        return instance

class CustomSignupForm(SignupForm):
    first_name = forms.CharField(max_length=30, label='First Name')
    last_name = forms.CharField(max_length=30, label='Last Name')
    def signup(self, request, user):
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.save()
        return user