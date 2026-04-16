from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.user_profile, name='profile'),
    path('api/totw/', views.get_team_of_the_week, name='get_totw'),
    path('api/notifications/', views.get_notifications, name='get_notifications'),
    path('api/notifications/read/', views.mark_notifications_read, name='mark_notifications_read'),
    path('', views.index, name='index'),
    path('auth/login/', views.auth_login, name='login'),
    path('auth/register/', views.auth_register, name='register'),
    path('auth/logout/', views.auth_logout, name='logout'),
    path('pick/', views.pick_team, name='pick_team'),
    path('pick/save/', views.save_picks, name='save_picks'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('fixtures/', views.fixtures, name='fixtures'),
    path('api/player/<int:player_id>/', views.get_player_detail, name='player_detail'),
    path('leagues/create/', views.create_league, name='create_league'),
    path('leagues/join/', views.join_league, name='join_league'),
    path('leagues/<str:code>/', views.league_detail, name='league_detail'),
]
