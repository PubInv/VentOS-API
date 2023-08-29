from django import forms
from .models import Person, Condition, Severity


class PostNewCommand(forms.Form):
    com = forms.CharField(label="com", max_length=1)
    par = forms.CharField(label="par", max_length=1)
    int = forms.CharField(label="int", max_length=1)
    mod = forms.IntegerField(min_value=0, max_value=255)
    val = forms.FloatField()


class PersonForm(forms.Form):
    data = Person.objects.all()
    patients_choices = []

    for i in range(len(data)):
        patients_choice = (data[i].id, data[i])
        patients_choices.append(patients_choice)

    chosen_patient = forms.CharField(label='Choose a patient: ',
                                     widget=forms.Select(choices=patients_choices))
    
    #repeat the same for conditions
    conditions = Condition.objects.all()
    condition_choices = []
    for i in range(len(conditions)):
        condition_choice = (conditions[i].id, conditions[i])
        condition_choices.append(condition_choice)

    chosen_condition = forms.CharField(label='Choose a condition',
                                       widget=forms.Select(choices=condition_choices))
    

    #repeat the same for severity
    severity = Severity.objects.all()
    severity_choices = []
    for i in range(len(severity)):
        severity_choice = (severity[i].id, severity[i])
        severity_choices.append(severity_choice)

    chosen_severity = forms.CharField(label='Choose severity',
                                       widget=forms.Select(choices=severity_choices),
                                       help_text="Ignore if 'normal' condition was chosen")