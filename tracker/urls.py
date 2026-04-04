from django.urls import path

from . import views

app_name = 'tracker'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('history/', views.history, name='history'),
    path('foods/', views.foods, name='foods'),
    path('foods/<int:food_id>/delete/', views.delete_food, name='delete_food'),
    path('goals/', views.goals, name='goals'),

    # HTMX endpoints
    path('htmx/search/', views.htmx_search, name='htmx_search'),
    path('htmx/log/add/', views.htmx_add_entry, name='htmx_add_entry'),
    path('htmx/log/import-and-add/', views.htmx_import_and_log, name='htmx_import_and_log'),
    path('htmx/log/<int:entry_id>/delete/', views.htmx_delete_entry, name='htmx_delete_entry'),
]
