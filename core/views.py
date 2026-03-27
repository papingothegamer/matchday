from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Team, Player, Gameweek, Match, FantasyTeam, FantasyPick


def index(request):
    context = {
        'num_teams': Team.objects.count(),
        'num_players': Player.objects.count(),
        'active_gameweek': Gameweek.objects.filter(is_active=True).first(),
        'recent_matches': Match.objects.filter(is_played=True).order_by('-match_date')[:5],
    }
    return render(request, 'core/index.html', context)


def pick_team(request):
    players = Player.objects.filter(is_active=True).select_related('team').order_by('position', '-price')
    context = {
        'players': players,
        'active_gameweek': Gameweek.objects.filter(is_active=True).first(),
    }
    return render(request, 'core/pick_team.html', context)


@csrf_exempt
def save_picks(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Login required'}, status=401)
    try:
        data = json.loads(request.body)
        picks = data.get('picks', [])
        gw = Gameweek.objects.filter(is_active=True).first()
        if not gw:
            return JsonResponse({'error': 'No active gameweek'})
        ft, _ = FantasyTeam.objects.get_or_create(
            user=request.user, gameweek=gw,
            defaults={'name': request.user.username + ' FC'}
        )
        ft.picks.all().delete()
        for pick in picks:
            player = Player.objects.get(id=pick['player_id'])
            FantasyPick.objects.create(
                fantasy_team=ft, player=player,
                is_captain=pick.get('is_captain', False)
            )
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'error': str(e)})
