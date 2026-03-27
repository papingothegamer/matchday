from django.shortcuts import render
from .models import Team, Player, Gameweek, Match


def index(request):
    context = {
        'num_teams': Team.objects.count(),
        'num_players': Player.objects.count(),
        'active_gameweek': Gameweek.objects.filter(is_active=True).first(),
        'recent_matches': Match.objects.filter(is_played=True).order_by('-match_date')[:5],
    }
    return render(request, 'core/index.html', context)
