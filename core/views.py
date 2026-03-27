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


from django.shortcuts import get_object_or_404


from django.shortcuts import get_object_or_404
from .models import Player, Team

def players_list(request):
    teams = Team.objects.all().order_by('name')
    return render(request, 'core/players.html', {'teams': teams})

def team_detail(request, short_name):
    team = get_object_or_404(Team, short_name=short_name)
    all_team_players = list(Player.objects.filter(team=team))
    
    # Real-Life 2025/2026 Starting XI Overrides for ultimate realism
    CORE_STARTERS = {
        'ARS': ['Raya', 'White', 'Saliba', 'Gabriel', 'Timber', 'Ødegaard', 'Rice', 'Saka', 'Zubimendi', 'Gyökeres', 'Eze'],
        'LIV': ['Becker', 'Alexander-Arnold', 'Konaté', 'van Dijk', 'Robertson', 'Szoboszlai', 'Mac Allister', 'Wirtz', 'Díaz', 'Isak', 'Ekitike'],
        'MCI': ['Trafford', 'Dias', 'Stones', 'Gvardiol', 'Aké', 'Rodri', 'De Bruyne', 'Foden', 'Bernardo Silva', 'Håland', 'Cherki'],
        'CHE': ['Sánchez', 'James', 'Colwill', 'Fofana', 'Cucurella', 'Caicedo', 'Fernández', 'Palmer', 'Neto', 'Nkunku', 'Jackson'],
        'MUN': ['Bayındır', 'Dalot', 'de Ligt', 'Martínez', 'Mazraoui', 'Mainoo', 'Ugarte', 'Fernandes', 'Garnacho', 'Rashford', 'Zirkzee'],
        'TOT': ['Vicario', 'Porro', 'Romero', 'van de Ven', 'Udogie', 'Sarr', 'Maddison', 'Kulusevski', 'Son', 'Johnson', 'Solanke'],
        'NEW': ['Pope', 'Trippier', 'Schär', 'Botman', 'Hall', 'Guimarães', 'Tonali', 'Joelinton', 'Gordon', 'Barnes', 'Wissa'],
        'AVL': ['Martínez', 'Cash', 'Konsa', 'Torres', 'Digne', 'Onana', 'Tielemans', 'McGinn', 'Bailey', 'Rogers', 'Watkins'],
        'WHU': ['Areola', 'Wan-Bissaka', 'Todibo', 'Kilman', 'Emerson', 'Álvarez', 'Souček', 'Paquetá', 'Bowen', 'Kudus', 'Fullkrug'],
        'BHA': ['Verbruggen', 'Veltman', 'van Hecke', 'Dunk', 'Estupiñán', 'Baleba', 'Wieffer', 'Minteh', 'Mitoma', 'Rutter', 'Welbeck']
    }
    
    team_core = CORE_STARTERS.get(short_name, [])
    
    # Advanced Sort: If player is in real-life starting XI, boost them to the top. Fallback to FPL Price.
    all_team_players.sort(key=lambda p: (
        p.last_name in team_core or p.first_name in team_core or f"{p.first_name} {p.last_name}".strip() in team_core,
        p.price
    ), reverse=True)

    gks = [p for p in all_team_players if p.position == 'GK']
    defs = [p for p in all_team_players if p.position == 'DEF']
    mids = [p for p in all_team_players if p.position == 'MID']
    fwds = [p for p in all_team_players if p.position == 'FWD']

    starters = []
    if gks: starters.append(gks.pop(0))
    for _ in range(min(4, len(defs))): starters.append(defs.pop(0))
    for _ in range(min(3, len(mids))): starters.append(mids.pop(0))
    for _ in range(min(3, len(fwds))): starters.append(fwds.pop(0))

    subs = gks[:1] + defs[:2] + mids[:2] + fwds[:2]
    reserves = [p for p in all_team_players if p not in starters and p not in subs]

    # Re-sort lists safely by position for the UI
    reserves.sort(key=lambda p: p.price, reverse=True)
    all_team_players.sort(key=lambda p: p.price, reverse=True)

    return render(request, 'core/team_detail.html', {
        'team': team, 'starters': starters, 'subs': subs, 'reserves': reserves, 'all_players': all_team_players
    })
