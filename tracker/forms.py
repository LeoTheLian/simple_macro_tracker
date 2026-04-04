from django import forms

from .models import DailyGoal, FoodItem, LogEntry


class LogEntryForm(forms.ModelForm):
    class Meta:
        model = LogEntry
        fields = ['food_item', 'date', 'serving_grams', 'meal_type']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'serving_grams': forms.NumberInput(attrs={'step': '0.1', 'min': '1', 'placeholder': 'grams'}),
        }


class AddLogEntryForm(forms.Form):
    """Lightweight form used by the HTMX 'Add to log' action."""
    food_item_id = forms.IntegerField(widget=forms.HiddenInput)
    date = forms.DateField(widget=forms.HiddenInput)
    serving_grams = forms.DecimalField(
        max_digits=8, decimal_places=1, min_value=1,
        widget=forms.NumberInput(attrs={'step': '0.1', 'min': '1', 'placeholder': '100'}),
    )
    meal_type = forms.ChoiceField(choices=LogEntry.MealType.choices)


class CustomFoodForm(forms.ModelForm):
    class Meta:
        model = FoodItem
        fields = ['name', 'calories_per_100g', 'protein_per_100g', 'carbs_per_100g', 'fat_per_100g']
        labels = {
            'calories_per_100g': 'Calories (per 100g)',
            'protein_per_100g': 'Protein g (per 100g)',
            'carbs_per_100g': 'Carbs g (per 100g)',
            'fat_per_100g': 'Fat g (per 100g)',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input-soft'}),
            'calories_per_100g': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'input-soft'}),
            'protein_per_100g': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'input-soft'}),
            'carbs_per_100g': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'input-soft'}),
            'fat_per_100g': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'input-soft'}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.source = FoodItem.Source.CUSTOM
        if commit:
            instance.save()
        return instance


class DailyGoalForm(forms.ModelForm):
    class Meta:
        model = DailyGoal
        fields = ['effective_date', 'calories', 'protein_g', 'carbs_g', 'fat_g']
        labels = {
            'effective_date': 'Apply from date',
            'calories': 'Calories (kcal)',
            'protein_g': 'Protein (g)',
            'carbs_g': 'Carbs (g)',
            'fat_g': 'Fat (g)',
        }
        widgets = {
            'effective_date': forms.DateInput(attrs={'type': 'date', 'class': 'input-soft'}),
            'calories': forms.NumberInput(attrs={'class': 'input-soft'}),
            'protein_g': forms.NumberInput(attrs={'class': 'input-soft'}),
            'carbs_g': forms.NumberInput(attrs={'class': 'input-soft'}),
            'fat_g': forms.NumberInput(attrs={'class': 'input-soft'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        calories = cleaned_data.get('calories')
        protein_g = cleaned_data.get('protein_g')
        carbs_g = cleaned_data.get('carbs_g')
        fat_g = cleaned_data.get('fat_g')

        if None in (calories, protein_g, carbs_g, fat_g):
            return cleaned_data

        expected_calories = (protein_g * 4) + (carbs_g * 4) + (fat_g * 9)
        if calories != expected_calories:
            self.add_error(
                'calories',
                (
                    f'Calories must equal macro calories: '
                    f'(protein*4 + carbs*4 + fat*9) = {expected_calories} kcal.'
                ),
            )

        return cleaned_data
