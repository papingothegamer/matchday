from django.urls import path
from . import views

urlpatterns = [
    # ===== Authentication =====
    path('auth/login/', views.auth_login, name='login'),
    path('auth/register/', views.auth_register, name='register'),
    path('auth/logout/', views.auth_logout, name='logout'),

    # ===== Coach Views =====
    path('', views.index, name='index'),
    path('tournaments/', views.tournament_list, name='tournament_list'),
    path('tournaments/<int:tournament_id>/', views.tournament_detail, name='tournament_detail'),
    path('tournaments/<int:tournament_id>/register/', views.register_team, name='register_team'),
    path('tournaments/<int:tournament_id>/teams/<int:team_id>/', views.team_detail, name='team_detail'),

    # ===== Tournament Admin Views =====
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('tournaments/create/', views.create_tournament, name='create_tournament'),
    path('tournaments/<int:tournament_id>/edit/', views.edit_tournament, name='edit_tournament'),
    path('tournaments/<int:tournament_id>/delete/', views.delete_tournament, name='delete_tournament'),
    path('tournaments/<int:tournament_id>/fixtures/', views.manage_fixtures, name='manage_fixtures'),
    path('matches/<int:match_id>/result/', views.enter_match_result, name='enter_match_result'),
    path('matches/<int:match_id>/auto-simulate/', views.auto_simulate_match, name='auto_simulate_match'),

    # ===== JSON APIs =====
    path('api/tournaments/<int:tournament_id>/standings/', views.api_standings, name='api_standings'),
    path('api/tournaments/<int:tournament_id>/top-scorers/', views.api_top_scorers, name='api_top_scorers'),
]