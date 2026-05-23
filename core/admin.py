from django.contrib import admin
from .models import (
    Team, Player, Tournament, TournamentTeam, Match, PlayerStat,
    Standing, KnockoutRound, KnockoutFixture,
)


class PlayerInline(admin.TabularInline):
    model = Player
    extra = 0


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_name', 'coach', 'primary_color')
    list_filter = ('coach',)
    inlines = [PlayerInline]


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'team', 'position', 'jersey_number', 'is_active')
    list_filter = ('team', 'position')
    search_fields = ('first_name', 'last_name')


class TournamentTeamInline(admin.TabularInline):
    model = TournamentTeam
    extra = 0


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ('name', 'format', 'status', 'created_by', 'created_at')
    list_filter = ('format', 'status')
    list_editable = ('status',)
    inlines = [TournamentTeamInline]


class PlayerStatInline(admin.TabularInline):
    model = PlayerStat
    extra = 0


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'tournament', 'round_label', 'home_score', 'away_score', 'is_played')
    list_filter = ('tournament', 'is_played', 'round_label')
    inlines = [PlayerStatInline]


@admin.register(PlayerStat)
class PlayerStatAdmin(admin.ModelAdmin):
    list_display = ('player', 'match', 'goals', 'assists', 'yellow_cards', 'red_cards', 'minutes_played')
    list_filter = ('match__tournament',)


@admin.register(Standing)
class StandingAdmin(admin.ModelAdmin):
    list_display = ('team', 'tournament', 'played', 'won', 'drawn', 'lost', 'goals_for', 'goals_against', 'goal_difference', 'points')
    list_filter = ('tournament',)
    ordering = ('-points', '-goal_difference')


@admin.register(KnockoutRound)
class KnockoutRoundAdmin(admin.ModelAdmin):
    list_display = ('round_name', 'tournament', 'round_order')
    list_filter = ('tournament',)


@admin.register(KnockoutFixture)
class KnockoutFixtureAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'round', 'winner')
    list_filter = ('round__tournament',)
