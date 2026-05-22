from django.contrib import admin
from .models import Team, Player, Gameweek, Match, FantasyTeam, FantasyPick, PlayerStat, Notification, League, LeagueMember, SquadApplication

@admin.register(Gameweek)
class GameweekAdmin(admin.ModelAdmin):
    list_display = ('number', 'deadline', 'is_active', 'is_finished')
    list_editable = ('is_active',)
    
    def is_finished(self, obj):
        return obj.matches.filter(is_played=False).count() == 0
    is_finished.boolean = True

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'match_date', 'gameweek', 'home_score', 'away_score', 'is_played')
    list_filter = ('gameweek', 'is_played')
    actions = ['simulate_selected_matches']

    def simulate_selected_matches(self, request, queryset):
        from core.simulation import simulate_match
        count = 0
        for match in queryset.filter(is_played=False):
            simulate_match(match)
            count += 1
        self.message_user(request, f"Successfully simulated {count} matches.")
    simulate_selected_matches.short_description = "Simulate selected matches now"

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'team', 'position', 'price', 'is_injured')
    list_filter = ('team', 'position', 'is_injured')
    search_fields = ('display_name',)

@admin.register(PlayerStat)
class PlayerStatAdmin(admin.ModelAdmin):
    list_display = ('player', 'match', 'minutes_played', 'goals', 'assists', 'fantasy_points', 'clean_sheet')
    list_filter = ('match__gameweek', 'clean_sheet')

admin.site.register(Team)
admin.site.register(FantasyTeam)
admin.site.register(FantasyPick)
admin.site.register(Notification)
admin.site.register(League)
admin.site.register(LeagueMember)

@admin.register(SquadApplication)
class SquadApplicationAdmin(admin.ModelAdmin):
    list_display = ('user', 'player1', 'player2', 'player3', 'status', 'submitted_at')
    list_filter = ('status',)
    list_editable = ('status',)
