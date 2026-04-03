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
@player_only
def save_picks(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        data = json.loads(request.body)
        picks = data.get('picks', [])
        formation = data.get('formation', '433')
        gw = Gameweek.objects.filter(is_active=True).first()
        if not gw:
            return JsonResponse({'error': 'No active gameweek'})
        ft, _ = FantasyTeam.objects.get_or_create(
            user=request.user, gameweek=gw,
            defaults={'name': request.user.username + ' FC'}
        )
        ft.formation = formation
        ft.save()
        ft.picks.all().delete()
        for pick in picks:
            player = Player.objects.get(id=pick['player_id'])
            FantasyPick.objects.create(
                fantasy_team=ft, player=player,
                is_captain=pick.get('is_captain', False),
                is_sub=pick.get('is_sub', False)
            )
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'error': str(e)})

def leaderboard(request):
    gameweeks = Gameweek.objects.all()
    from django.contrib.auth.models import User

    global_rankings = []
    for user in User.objects.filter(fantasy_teams__isnull=False).distinct():
        teams = FantasyTeam.objects.filter(user=user)
        total = teams.aggregate(t=Sum('total_points'))['t'] or 0
        gw_scores = list(teams.order_by('gameweek__number').values_list('total_points', flat=True))
        global_rankings.append({'user': user, 'total': total, 'gw_scores': gw_scores[-5:]})
    global_rankings.sort(key=lambda x: x['total'], reverse=True)
    for i, r in enumerate(global_rankings):
        r['rank'] = i + 1

    selected_gw_num = request.GET.get('gw')
    selected_gw = Gameweek.objects.filter(number=selected_gw_num).first() if selected_gw_num else None
    if not selected_gw:
        selected_gw = Gameweek.objects.filter(is_active=True).first()
    gw_standings = []
    if selected_gw:
        gw_standings = list(FantasyTeam.objects.filter(gameweek=selected_gw).select_related('user').order_by('-total_points'))
        for i, ft in enumerate(gw_standings):
            ft.rank = i + 1

    top_scorers = (
        Player.objects.filter(stats__isnull=False)
        .annotate(total_pts=Sum('stats__fantasy_points'), total_goals=Sum('stats__goals'), total_assists=Sum('stats__assists'))
        .order_by('-total_pts')[:50]
    )

    last5_gws = list(Gameweek.objects.order_by('-number')[:5])
    last5_gws.reverse()
    form_data = []
    for user in User.objects.filter(fantasy_teams__isnull=False).distinct():
        row = {'user': user, 'scores': [], 'total': 0}
        for gw in last5_gws:
            ft = FantasyTeam.objects.filter(user=user, gameweek=gw).first()
            pts = ft.total_points if ft else None
            row['scores'].append(pts)
            if pts:
                row['total'] += pts
        form_data.append(row)
    form_data.sort(key=lambda x: x['total'], reverse=True)

    user_leagues = []
    if request.user.is_authenticated:
        user_leagues = League.objects.filter(members__user=request.user)

    context = {
        'global_rankings': global_rankings, 'gameweeks': gameweeks,
        'selected_gw': selected_gw, 'gw_standings': gw_standings,
        'top_scorers': top_scorers, 'last5_gws': last5_gws,
        'form_data': form_data, 'user_leagues': user_leagues,
    }
    return render(request, 'core/leaderboard.html', context)


@login_required
@player_only
def create_league(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            league = League.objects.create(name=name, created_by=request.user)
            LeagueMember.objects.create(league=league, user=request.user)
            return redirect('league_detail', code=league.code)
    return render(request, 'core/create_league.html')


@login_required
@player_only
def join_league(request):
    if request.method == 'POST':
        code = request.POST.get('code', '').strip().upper()
        league = League.objects.filter(code=code).first()
        if not league:
            return render(request, 'core/join_league.html', {'error': 'Invalid code.'})
        LeagueMember.objects.get_or_create(league=league, user=request.user)
        return redirect('league_detail', code=league.code)
    return render(request, 'core/join_league.html')


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
