from django import forms
from .models import Application, Region, School

class ApplicationForm(forms.ModelForm):
    region = forms.ModelChoiceField(
        queryset=Region.objects.all().order_by('name'),
        label="Qaysi tumanda yashaysiz?",
        empty_label="Tanlang...",
        widget=forms.Select(attrs={
            'class': 'w-full rounded-lg border border-slate-200 dark:border-[#323b67] bg-slate-50 dark:bg-[#101322] p-3 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all'
        })
    )
    
    school = forms.ModelChoiceField(
        queryset=School.objects.none(),
        label="Maktab nomi",
        empty_label="Tanlang...",
        required=False,  # Initially false because it might not be shown
        widget=forms.Select(attrs={
            'class': 'w-full rounded-lg border border-slate-200 dark:border-[#323b67] bg-slate-50 dark:bg-[#101322] p-3 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all'
        })
    )

    class Meta:
        model = Application
        fields = ['region', 'school', 'grade', 'english_level', 'device', 'about']
        labels = {
            'grade': "Nechanchi sinfda o'qiysiz?",
            'english_level': "Ingliz tili darajasi",
            'device': "Jihozingiz",
            'about': "O'zingiz haqingizda qisqacha"
        }
        widgets = {
            'grade': forms.Select(attrs={'class': 'w-full rounded-lg border border-slate-200 dark:border-[#323b67] bg-slate-50 dark:bg-[#101322] p-3 text-slate-900 dark:text-white'}),
            'english_level': forms.Select(attrs={'class': 'w-full rounded-lg border border-slate-200 dark:border-[#323b67] bg-slate-50 dark:bg-[#101322] p-3 text-slate-900 dark:text-white'}),
            'device': forms.Select(attrs={'class': 'w-full rounded-lg border border-slate-200 dark:border-[#323b67] bg-slate-50 dark:bg-[#101322] p-3 text-slate-900 dark:text-white'}),
            'about': forms.Textarea(attrs={'class': 'w-full rounded-lg border border-slate-200 dark:border-[#323b67] bg-slate-50 dark:bg-[#101322] p-3 text-slate-900 dark:text-white', 'rows': 3, 'placeholder': 'Qobiliyatlaringiz va qiziqishlaringiz...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Default empty queryset for school
        self.fields['school'].queryset = School.objects.none()
        
        # If 'region' is in data (POST request), populate schools
        if 'region' in self.data:
            try:
                region_id = int(self.data.get('region'))
                self.fields['school'].queryset = School.objects.filter(region_id=region_id).order_by('name')
            except (ValueError, TypeError):
                pass 
        elif self.instance.pk:
            # If editing an existing application
            self.fields['school'].queryset = self.instance.region.school_set.order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        region = cleaned_data.get('region')
        school = cleaned_data.get('school')
        
        # If region is selected, verify it's open
        if region and not region.is_open:
            raise forms.ValidationError(f"{region.name} hududida qabul tugagan.") 
            # This error prevents saving even if they bypass UI
        
        # If region is open, school represents a required field
        if region and region.is_open:
            if not school:
                self.add_error('school', "Maktabni tanlang")
        
        return cleaned_data
#
