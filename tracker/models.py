from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class FoodItem(models.Model):
    class Source(models.TextChoices):
        USDA = 'USDA', 'USDA'
        CUSTOM = 'CUSTOM', 'Custom'

    name = models.CharField(max_length=255)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.CUSTOM)
    usda_fdc_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    calories_per_100g = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    protein_per_100g = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    carbs_per_100g = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    fat_per_100g = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def macros_for_serving(self, serving_grams):
        """Return dict of actual macro amounts for a given serving size in grams."""
        factor = Decimal(str(serving_grams)) / Decimal('100')
        return {
            'calories': round(self.calories_per_100g * factor, 1),
            'protein': round(self.protein_per_100g * factor, 1),
            'carbs': round(self.carbs_per_100g * factor, 1),
            'fat': round(self.fat_per_100g * factor, 1),
        }


class LogEntry(models.Model):
    class MealType(models.TextChoices):
        BREAKFAST = 'BREAKFAST', 'Breakfast'
        LUNCH = 'LUNCH', 'Lunch'
        DINNER = 'DINNER', 'Dinner'
        SNACK = 'SNACK', 'Snack'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='log_entries',
    )
    date = models.DateField(default=timezone.now)
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name='log_entries')
    serving_grams = models.DecimalField(max_digits=8, decimal_places=1)
    meal_type = models.CharField(
        max_length=10, choices=MealType.choices, default=MealType.SNACK
    )
    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['meal_type', 'logged_at']

    def __str__(self):
        return f'{self.date} — {self.food_item.name} ({self.serving_grams}g)'

    @property
    def macros(self):
        return self.food_item.macros_for_serving(self.serving_grams)


class DailyGoal(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='daily_goals',
    )
    effective_date = models.DateField(default=timezone.now)
    calories = models.PositiveIntegerField(default=2000)
    protein_g = models.PositiveIntegerField(default=150)
    carbs_g = models.PositiveIntegerField(default=200)
    fat_g = models.PositiveIntegerField(default=65)

    class Meta:
        ordering = ['-effective_date']
        constraints = [
            models.UniqueConstraint(fields=['user', 'effective_date'], name='unique_user_goal_date'),
        ]

    def __str__(self):
        return f'Goal from {self.effective_date}: {self.calories} kcal'
