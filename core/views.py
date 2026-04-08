from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test

player_only = user_passes_test(lambda u: not u.is_staff, login_url='/admin/')
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum
import json
from .models import Team, Player, Gameweek, Match, FantasyTeam, FantasyPick, PlayerStat, League, LeagueMember


def auth_login(request):
    if request.user.is_authenticated:
        return redirect('index')
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            if user.is_staff:
                error = 'Administrators must log in via the /admin/ portal.'
            else:
                login(request, user)
                return redirect(request.GET.get('next', '/'))
        error = 'Invalid username or password.'
    return render(request, 'core/auth/login.html', {'error': error})


def auth_register(request):
    if request.user.is_authenticated:
        return redirect('index')
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm', '')
        if not username or not password:
            error = 'All fields are required.'
        elif password != confirm:
            error = 'Passwords do not match.'
        elif User.objects.filter(username=username).exists():
            error = 'Username already taken.'
        elif len(password) < 8:
            error = 'Password must be at least 8 characters.'
        else:
            user = User.objects.create_user(username=username, password=password)
            login(request, user)
            return redirect('/')
    return render(request, 'core/auth/register.html', {'error': error})


def auth_logout(request):
    logout(request)
    return redirect('/auth/login/')


def index(request):
    active_gw = Gameweek.objects.filter(is_active=True).first()
    user_team = None
    prev_points = None
    picks = []

    if request.user.is_authenticated and active_gw:
        user_team = FantasyTeam.objects.filter(user=request.user, gameweek=active_gw).first()
        if not user_team:
            user_team = FantasyTeam.objects.filter(user=request.user).order_by("-gameweek__number").first()
        if user_team:
            picks = list(user_team.picks.select_related('player__team').all())

        prev_gw = Gameweek.objects.filter(number=active_gw.number - 1).first()
        if prev_gw:
            prev_team = FantasyTeam.objects.filter(user=request.user, gameweek=prev_gw).first()
            if prev_team:
                prev_points = prev_team.total_points

    context = {
        'num_teams': Team.objects.count(),
        'num_players': Player.objects.count(),
        'active_gameweek': active_gw,
        'recent_matches': Match.objects.filter(is_played=True).order_by('-match_date')[:5],
        'user_team': user_team,
        'picks': picks,
        'prev_points': prev_points,
    }
    return render(request, 'core/index.html', context)


@login_required
@player_only
def pick_team(request):
    players = Player.objects.filter(is_active=True).select_related('team').order_by('position', '-price')
    active_gw = Gameweek.objects.filter(is_active=True).first()
    existing_picks = []
    saved_formation = '433'
    if active_gw:
        ft = FantasyTeam.objects.filter(user=request.user, gameweek=active_gw).first()
        if not ft:
            ft = FantasyTeam.objects.filter(user=request.user).order_by("-gameweek__number").first()
        if ft:
            saved_formation = ft.formation
            for pick in ft.picks.all():
                existing_picks.append({
                    'id': pick.player.id,
                    'pos': pick.player.position,
                    'is_sub': pick.is_sub,
                    'is_captain': pick.is_captain
                })
    context = {
        'players': players,
        'active_gameweek': active_gw,
        'saved_picks_json': json.dumps(existing_picks),
        'saved_formation': saved_formation,
    }
    return render(request, 'core/pick_team.html', context)

@csrf_exempt
@login_required
def league_detail(request, code):
    league = get_object_or_404(League, code=code)
    members = LeagueMember.objects.filter(league=league).select_related('user')
    rankings = []
    for member in members:
        teams = FantasyTeam.objects.filter(user=member.user)
        total = teams.aggregate(t=Sum('total_points'))['t'] or 0
        gw_scores = list(teams.order_by('gameweek__number').values_list('total_points', flat=True))
        rankings.append({'user': member.user, 'total': total, 'gw_scores': gw_scores[-5:]})
    rankings.sort(key=lambda x: x['total'], reverse=True)
    for i, r in enumerate(rankings):
        r['rank'] = i + 1
    context = {
        'league': league, 'rankings': rankings,
        'is_member': request.user.is_authenticated and members.filter(user=request.user).exists(),
    }
    return render(request, 'core/league_detail.html', context)

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import Notification

@login_required
def get_notifications(request):
    notifs = Notification.objects.filter(user=request.user).order_by('-created_at')[:15]
    data = [{
        'id': n.id,
        'message': n.message,
        'is_read': n.is_read,
        'date': n.created_at.strftime("%b %d, %H:%M")
    } for n in notifs]
    return JsonResponse({'notifications': data})

@csrf_exempt
@login_required
def mark_notifications_read(request):
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'ok': True})
    return JsonResponse({'error': 'POST required'}, status=405)

@login_required
def get_team_of_the_week(request):
    from .models import Match, PlayerStat
    
    # Strictly find the latest Gameweek where matches were ACTUALLY played
    latest_match = Match.objects.filter(is_played=True).order_by('-gameweek__number').first()
    if not latest_match:
        return JsonResponse({'error': 'No matches played yet'})
    
    gw = latest_match.gameweek
    totw_players = []
    
    def get_top_players(pos, count):
        stats = PlayerStat.objects.filter(match__gameweek=gw, player__position=pos).order_by('-fantasy_points')[:count]
        for s in stats:
            totw_players.append({
                'name': s.player.display_name,
                'team': s.player.team.short_name,
                'pos': s.player.position,
                'color': s.player.team.primary_color,
                'color2': s.player.team.secondary_color,
                'pts': s.fantasy_points,
                'is_captain': False
            })

    get_top_players('GK', 1)
    get_top_players('DEF', 3)
    get_top_players('MID', 4)
    get_top_players('FWD', 3)

    if totw_players:
        top_scorer = max(totw_players, key=lambda p: p['pts'])
        top_scorer['is_captain'] = True

    return JsonResponse({'gameweek': gw.number, 'players': totw_players})
    gw = latest_match.gameweek

    # Dynamic 3-4-3 Formation for TOTW
    totw_players = []
    
    def get_top_players(pos, count):
        stats = PlayerStat.objects.filter(match__gameweek=gw, player__position=pos).order_by('-fantasy_points')[:count]
        for s in stats:
            totw_players.append({
                'name': s.player.display_name,
                'team': s.player.team.short_name,
                'pos': s.player.position,
                'color': s.player.team.primary_color,
                'color2': s.player.team.secondary_color,
                'pts': s.fantasy_points,
                'is_captain': False
            })

    get_top_players('GK', 1)
    get_top_players('DEF', 3)
    get_top_players('MID', 4)
    get_top_players('FWD', 3)

    if totw_players:
        top_scorer = max(totw_players, key=lambda p: p['pts'])
        top_scorer['is_captain'] = True

    return JsonResponse({'gameweek': gw.number, 'players': totw_players})

@login_required
def create_league(request):
    from django.shortcuts import render, redirect, get_object_or_404
    from .models import League, LeagueMember
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            league = League.objects.create(name=name, created_by=request.user)
            # Fix: Automatically add the creator as a member!
            LeagueMember.objects.create(league=league, user=request.user)
            return redirect('league_detail', code=league.code)
    return render(request, 'core/create_league.html')

@login_required
def join_league(request):
    from django.shortcuts import render, redirect, get_object_or_404
    from .models import League, LeagueMember
    if request.method == 'POST':
        code = request.POST.get('code')
        if code:
            # Fix: Look up by Share Code and redirect properly
            league = get_object_or_404(League, code=code)
            LeagueMember.objects.get_or_create(league=league, user=request.user)
            return redirect('league_detail', code=league.code)
    return render(request, 'core/join_league.html')

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@login_required
def save_picks(request):
    import json
    from django.http import JsonResponse
    from .models import Gameweek, FantasyTeam, Player, FantasyPick
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            picks = data.get('picks', [])
            formation = data.get('formation', '433')
            
            active_gw = Gameweek.objects.filter(is_active=True).first()
            if not active_gw:
                return JsonResponse({'error': 'No active gameweek'})
                
            ft, created = FantasyTeam.objects.get_or_create(user=request.user, gameweek=active_gw)
            ft.formation = formation
            ft.save()
            
            # Clear old picks and save the new 15-man roster
            ft.picks.all().delete()
            
            for p in picks:
                try:
                    player = Player.objects.get(id=p['player_id'])
                    FantasyPick.objects.create(
                        fantasy_team=ft,
                        player=player,
                        is_captain=p.get('is_captain', False),
                        is_sub=p.get('is_sub', False)
                    )
                except Exception:
                    pass
                    
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)})
            
    return JsonResponse({'error': 'POST required'}, status=405)
