from django.urls import path
from . import views

urlpatterns = [
    # ===== SCAFFOLD: Dashboard & Approval CRUD =====
    path('', views.index, name='index'),
    path('apply/', views.submit_application, name='submit_application'),
    path('approve/<int:pk>/', views.approve_application, name='approve_application'),
    path('delete/<int:pk>/', views.delete_application, name='delete_application'),
    path('simulate_squad/<int:pk>/', views.simulate_squad, name='simulate_squad'),

    # ===== Authentication (kept intact) =====
    path('auth/login/', views.auth_login, name='login'),
    path('auth/register/', views.auth_register, name='register'),
    path('auth/logout/', views.auth_logout, name='logout'),

    # ===== Global Leaderboard =====
    path('leaderboard/', views.leaderboard, name='leaderboard'),

    # ===== Original Feature Routes (preserved, commented for scaffold) =====
    # These routes power the full simulation engine and are kept intact
    # in the backend. Uncomment to restore full functionality.
    #
    # path('profile/', views.user_profile, name='profile'),
    # path('api/totw/', views.get_team_of_the_week, name='get_totw'),
    # path('api/notifications/', views.get_notifications, name='get_notifications'),
    # path('api/notifications/read/', views.mark_notifications_read, name='mark_notifications_read'),
    # path('pick/', views.pick_team, name='pick_team'),
    # path('pick/save/', views.save_picks, name='save_picks'),
    # path('leaderboard/', views.leaderboard, name='leaderboard'),
    # path('fixtures/', views.fixtures, name='fixtures'),
    # path('api/player/<int:player_id>/', views.get_player_detail, name='player_detail'),
    # path('leagues/create/', views.create_league, name='create_league'),
    # path('leagues/join/', views.join_league, name='join_league'),
    # path('leagues/<str:code>/', views.league_detail, name='league_detail'),
    # path('leagues/<str:code>/leave/', views.leave_league, name='leave_league'),
    # path('leagues/<str:code>/delete/', views.delete_league, name='delete_league'),
    # path('players/', views.players, name='players'),
    # path('teams/<str:short_name>/', views.team_detail, name='team_detail'),
    # path('simulate/', views.simulation_center, name='simulation_center'),
    # path('architecture/', views.architecture_view, name='architecture_view'),
]