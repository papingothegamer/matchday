from django.contrib import admin
from .models import Team, Player, Gameweek, Match, PlayerStat, FantasyTeam, FantasyPick


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_name', 'stadium', 'founded_year')


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'team', 'position', 'price', 'is_active')
    list_filter = ('position', 'team', 'is_active')
    search_fields = ('first_name', 'last_name')


@admin.register(Gameweek)
class GameweekAdmin(admin.ModelAdmin):
    list_display = ('number', 'deadline', 'is_active')


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'match_date', 'home_score', 'away_score', 'is_played')
    list_filter = ('gameweek', 'is_played')


@admin.register(PlayerStat)
class PlayerStatAdmin(admin.ModelAdmin):
    list_display = ('player', 'match', 'goals', 'assists', 'minutes_played', 'clean_sheet', 'fantasy_points')


@admin.register(FantasyTeam)
class FantasyTeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'gameweek', 'total_points')


@admin.register(FantasyPick)
class FantasyPickAdmin(admin.ModelAdmin):
    list_display = ('player', 'fantasy_team', 'is_captain', 'points_scored')
