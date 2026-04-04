"""
USDA FoodData Central API client.

Nutrient IDs:
  1008 = Energy (kcal)
  1003 = Protein (g)
  1005 = Carbohydrate, by difference (g)
  1004 = Total lipid / fat (g)

API base: https://api.nal.usda.gov/fdc/v1/
Docs:     https://fdc.nal.usda.gov/api-guide.html
"""

import os

import httpx

FDC_BASE = 'https://api.nal.usda.gov/fdc/v1'
NUTRIENT_MAP = {
    1008: 'calories',
    1003: 'protein',
    1005: 'carbs',
    1004: 'fat',
}


def _api_key():
    key = os.getenv('USDA_API_KEY', 'DEMO_KEY')
    if not key:
        raise EnvironmentError('USDA_API_KEY is not set in environment variables.')
    return key


def search_foods(query: str, page_size: int = 20) -> list[dict]:
    """
    Search USDA FoodData Central and return a simplified list of food dicts.

    Each dict has:  fdcId, name, calories, protein, carbs, fat  (all per 100g)
    """
    params = {
        'api_key': _api_key(),
        'query': query,
        'pageSize': page_size,
        'dataType': 'Foundation,SR Legacy,Branded',
    }
    try:
        resp = httpx.get(f'{FDC_BASE}/foods/search', params=params, timeout=10)
        resp.raise_for_status()
    except httpx.TimeoutException:
        return []
    except httpx.HTTPStatusError:
        return []

    foods = resp.json().get('foods', [])
    results = []
    for food in foods:
        nutrients = _extract_from_search_result(food.get('foodNutrients', []))
        results.append({
            'fdcId': food['fdcId'],
            'name': food.get('description', 'Unknown'),
            **nutrients,
        })
    return results


def get_food_detail(fdc_id: int) -> dict | None:
    """Fetch full food detail by FDC ID and return raw JSON dict, or None on error."""
    params = {'api_key': _api_key()}
    try:
        resp = httpx.get(f'{FDC_BASE}/food/{fdc_id}', params=params, timeout=10)
        resp.raise_for_status()
    except (httpx.TimeoutException, httpx.HTTPStatusError):
        return None
    return resp.json()


def extract_nutrients(food_json: dict) -> dict:
    """
    Extract per-100g macro values from a food detail JSON response.
    Returns dict with keys: calories, protein, carbs, fat.
    """
    nutrient_list = food_json.get('foodNutrients', [])
    result = {'calories': 0.0, 'protein': 0.0, 'carbs': 0.0, 'fat': 0.0}
    for entry in nutrient_list:
        # Detail endpoint nests the nutrient under a 'nutrient' sub-object
        nutrient = entry.get('nutrient', {})
        nid = nutrient.get('id')
        if nid in NUTRIENT_MAP:
            result[NUTRIENT_MAP[nid]] = entry.get('amount', 0.0) or 0.0
    return result


def import_usda_food(fdc_id: int):
    """
    Fetch a food from USDA, cache it as a FoodItem in the DB, and return it.
    Uses get_or_create so repeated calls for the same fdcId are a no-op.
    Returns (FoodItem, created) tuple, or (None, False) on API error.
    """
    # Import here to avoid circular import at module level
    from tracker.models import FoodItem

    # Return cached version if already imported
    try:
        existing = FoodItem.objects.get(usda_fdc_id=fdc_id)
        return existing, False
    except FoodItem.DoesNotExist:
        pass

    food_json = get_food_detail(fdc_id)
    if food_json is None:
        return None, False

    nutrients = extract_nutrients(food_json)
    name = food_json.get('description', f'USDA Food {fdc_id}')

    food_item = FoodItem.objects.create(
        name=name,
        source=FoodItem.Source.USDA,
        usda_fdc_id=fdc_id,
        calories_per_100g=nutrients['calories'],
        protein_per_100g=nutrients['protein'],
        carbs_per_100g=nutrients['carbs'],
        fat_per_100g=nutrients['fat'],
    )
    return food_item, True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_from_search_result(nutrient_list: list) -> dict:
    """
    The /foods/search endpoint returns nutrient data in a flat list with a
    'nutrientId' key (not nested under 'nutrient').
    """
    result = {'calories': 0.0, 'protein': 0.0, 'carbs': 0.0, 'fat': 0.0}
    for entry in nutrient_list:
        nid = entry.get('nutrientId')
        if nid in NUTRIENT_MAP:
            result[NUTRIENT_MAP[nid]] = entry.get('value', 0.0) or 0.0
    return result
