from django.contrib import admin

from .models import DailyGoal, FoodItem, LogEntry


@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'source', 'calories_per_100g', 'protein_per_100g', 'carbs_per_100g', 'fat_per_100g']
    list_filter = ['source']
    search_fields = ['name']


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'food_item', 'serving_grams', 'meal_type', 'logged_at']
    list_filter = ['user', 'date', 'meal_type']
    date_hierarchy = 'date'


@admin.register(DailyGoal)
class DailyGoalAdmin(admin.ModelAdmin):
    list_display = ['user', 'effective_date', 'calories', 'protein_g', 'carbs_g', 'fat_g']
    list_filter = ['user']
