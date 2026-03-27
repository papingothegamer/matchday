from django.urls import path
from . import views

urlpatterns = [
    path('players/', views.players_list, name='players'),
    path('', views.index, name='index'),
    path('pick/', views.pick_team, name='pick_team'),
    path('pick/save/', views.save_picks, name='save_picks'),
]
