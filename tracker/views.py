import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import AddLogEntryForm, CustomFoodForm, DailyGoalForm
from .models import DailyGoal, FoodItem, LogEntry
from .services import usda as usda_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date_param(request) -> date:
    """Return date from ?date= query param, defaulting to today."""
    raw = request.GET.get('date') or request.POST.get('date')
    if raw:
        parsed = parse_date(raw)
        if parsed:
            return parsed
    return date.today()


def _get_current_goal(user) -> DailyGoal | None:
    """Return the most recent DailyGoal for the given user, or None."""
    return DailyGoal.objects.filter(user=user).order_by('-effective_date').first()


def _totals_for_entries(entries) -> dict:
    totals = {'calories': Decimal('0'), 'protein': Decimal('0'),
               'carbs': Decimal('0'), 'fat': Decimal('0')}
    for entry in entries:
        m = entry.macros
        for key in totals:
            totals[key] += m[key]
    return {k: round(v, 1) for k, v in totals.items()}


def _progress(current, goal_value) -> int:
    """Return integer percentage (0-100) capped at 100."""
    if not goal_value:
        return 0
    return min(100, int(current / goal_value * 100))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
@require_GET
def dashboard(request):
    current_date = _parse_date_param(request)
    prev_date = current_date - timedelta(days=1)
    next_date = current_date + timedelta(days=1)

    entries = (
        LogEntry.objects
        .filter(user=request.user, date=current_date)
        .select_related('food_item')
        .order_by('meal_type', 'logged_at')
    )
    totals = _totals_for_entries(entries)
    goal = _get_current_goal(request.user)

    context = {
        'current_date': current_date,
        'today': date.today(),
        'prev_date': prev_date,
        'next_date': next_date,
        'entries': entries,
        'totals': totals,
        'goal': goal,
        'progress': {
            'calories': _progress(totals['calories'], goal.calories if goal else 0),
            'protein': _progress(totals['protein'], goal.protein_g if goal else 0),
            'carbs': _progress(totals['carbs'], goal.carbs_g if goal else 0),
            'fat': _progress(totals['fat'], goal.fat_g if goal else 0),
        },
        'add_form': AddLogEntryForm(initial={'date': current_date, 'meal_type': 'SNACK'}),
    }
    return render(request, 'tracker/dashboard.html', context)


# ---------------------------------------------------------------------------
# HTMX: food search
# ---------------------------------------------------------------------------

@login_required
@require_GET
def htmx_search(request):
    query = request.GET.get('q', '').strip()
    usda_results = []
    custom_results = []

    if len(query) >= 2:
        # Search custom foods first (instant, from DB)
        custom_results = list(
            FoodItem.objects.filter(name__icontains=query).order_by('source', 'name')[:10]
        )
        # Then USDA API
        usda_results = usda_service.search_foods(query, page_size=10)

    current_date = _parse_date_param(request)
    return render(request, 'tracker/partials/food_search_results.html', {
        'usda_results': usda_results,
        'custom_results': custom_results,
        'current_date': current_date,
    })


# ---------------------------------------------------------------------------
# HTMX: add log entry
# ---------------------------------------------------------------------------

@login_required
@require_POST
def htmx_add_entry(request):
    current_date = _parse_date_param(request)
    form = AddLogEntryForm(request.POST)

    if not form.is_valid():
        # Return a small error fragment
        return HttpResponse(
            f'<p class="text-red-500 text-sm">Invalid input: {form.errors.as_text()}</p>',
            status=422,
        )

    food_item_id = form.cleaned_data['food_item_id']
    log_date = form.cleaned_data['date']
    serving_grams = form.cleaned_data['serving_grams']
    meal_type = form.cleaned_data['meal_type']

    # Food might be a DB item or a USDA fdcId we need to import
    try:
        food_item = FoodItem.objects.get(pk=food_item_id)
    except FoodItem.DoesNotExist:
        # food_item_id is treated as an fdcId to import
        food_item, _ = usda_service.import_usda_food(food_item_id)
        if food_item is None:
            return HttpResponse(
                '<p class="text-red-500 text-sm">Could not import food from USDA.</p>',
                status=502,
            )

    LogEntry.objects.create(
        user=request.user,
        date=log_date,
        food_item=food_item,
        serving_grams=serving_grams,
        meal_type=meal_type,
    )

    return _render_log_and_summary(request, log_date)


# ---------------------------------------------------------------------------
# HTMX: delete log entry
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(['DELETE'])
def htmx_delete_entry(request, entry_id):
    entry = get_object_or_404(LogEntry, pk=entry_id, user=request.user)
    log_date = entry.date
    entry.delete()
    return _render_log_and_summary(request, log_date)


# ---------------------------------------------------------------------------
# HTMX: import USDA food and immediately log it
# ---------------------------------------------------------------------------

@login_required
@require_POST
def htmx_import_and_log(request):
    """
    Called when user selects a USDA result. Imports the FoodItem (cached)
    then delegates to htmx_add_entry logic by re-submitting with the new DB id.
    """
    fdc_id = request.POST.get('fdc_id')
    if not fdc_id or not fdc_id.isdigit():
        return HttpResponse('<p class="text-red-500 text-sm">Invalid food ID.</p>', status=400)

    food_item, _ = usda_service.import_usda_food(int(fdc_id))
    if food_item is None:
        return HttpResponse(
            '<p class="text-red-500 text-sm">Could not import food from USDA.</p>', status=502
        )

    log_date_str = request.POST.get('date', str(date.today()))
    serving_grams = request.POST.get('serving_grams', '100')
    meal_type = request.POST.get('meal_type', 'SNACK')

    log_date = parse_date(log_date_str) or date.today()

    LogEntry.objects.create(
        user=request.user,
        date=log_date,
        food_item=food_item,
        serving_grams=serving_grams,
        meal_type=meal_type,
    )

    return _render_log_and_summary(request, log_date)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@login_required
@require_GET
def history(request):
    from django.db.models import Sum
    from django.db.models.functions import Cast
    from django.db.models import FloatField

    days = (
        LogEntry.objects
        .filter(user=request.user)
        .values('date')
        .order_by('-date')
        .distinct()
    )

    # Build list with total calories per day
    history_items = []
    for day in days:
        d = day['date']
        entries = LogEntry.objects.filter(user=request.user, date=d).select_related('food_item')
        totals = _totals_for_entries(entries)
        history_items.append({'date': d, 'calories': totals['calories']})

    return render(request, 'tracker/history.html', {'history_items': history_items})


# ---------------------------------------------------------------------------
# Custom Foods
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(['GET', 'POST'])
def foods(request):
    if request.method == 'POST':
        form = CustomFoodForm(request.POST)
        if form.is_valid():
            form.save()
            if request.headers.get('HX-Request'):
                custom_foods = FoodItem.objects.filter(source=FoodItem.Source.CUSTOM)
                form = CustomFoodForm()
                return render(request, 'tracker/partials/custom_food_table.html', {
                    'custom_foods': custom_foods,
                    'form': form,
                })
            return redirect('tracker:foods')
    else:
        form = CustomFoodForm()

    custom_foods = FoodItem.objects.filter(source=FoodItem.Source.CUSTOM)
    return render(request, 'tracker/foods.html', {'custom_foods': custom_foods, 'form': form})


@login_required
@require_http_methods(['DELETE'])
def delete_food(request, food_id):
    food = get_object_or_404(FoodItem, pk=food_id, source=FoodItem.Source.CUSTOM)
    food.delete()
    custom_foods = FoodItem.objects.filter(source=FoodItem.Source.CUSTOM)
    form = CustomFoodForm()
    return render(request, 'tracker/partials/custom_food_table.html', {
        'custom_foods': custom_foods,
        'form': form,
    })


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(['GET', 'POST'])
def goals(request):
    latest_goal = _get_current_goal(request.user)

    if request.method == 'POST':
        form = DailyGoalForm(request.POST, instance=latest_goal)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            # If effective_date already has a goal for this user, update it; else create new
            existing = DailyGoal.objects.filter(user=request.user, effective_date=obj.effective_date).first()
            if existing and existing != latest_goal:
                for field in ['calories', 'protein_g', 'carbs_g', 'fat_g']:
                    setattr(existing, field, getattr(obj, field))
                existing.save()
            else:
                obj.save()
            return redirect('tracker:goals')
    else:
        import datetime
        form = DailyGoalForm(
            instance=latest_goal,
            initial={'effective_date': datetime.date.today()},
        )

    return render(request, 'tracker/goals.html', {'form': form, 'goal': latest_goal})


# ---------------------------------------------------------------------------
# Internal: build combined log+summary response for HTMX
# ---------------------------------------------------------------------------

def _render_log_and_summary(request, log_date):
    entries = (
        LogEntry.objects
        .filter(user=request.user, date=log_date)
        .select_related('food_item')
        .order_by('meal_type', 'logged_at')
    )
    totals = _totals_for_entries(entries)
    goal = _get_current_goal(request.user)
    progress = {
        'calories': _progress(totals['calories'], goal.calories if goal else 0),
        'protein': _progress(totals['protein'], goal.protein_g if goal else 0),
        'carbs': _progress(totals['carbs'], goal.carbs_g if goal else 0),
        'fat': _progress(totals['fat'], goal.fat_g if goal else 0),
    }
    add_form = AddLogEntryForm(initial={'date': log_date, 'meal_type': 'SNACK'})

    # Render the log table (primary swap target)
    log_html = render(request, 'tracker/partials/log_table.html', {
        'entries': entries,
        'totals': totals,
        'current_date': log_date,
        'add_form': add_form,
    }).content.decode()

    # Render the macro summary as an OOB swap
    summary_html = render(request, 'tracker/partials/macro_summary.html', {
        'totals': totals,
        'goal': goal,
        'progress': progress,
    }).content.decode()

    return HttpResponse(log_html + summary_html)
