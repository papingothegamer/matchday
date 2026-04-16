from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum
import json
import math
from .models import Team, Player, Gameweek, Match, FantasyTeam, FantasyPick, PlayerStat, League, LeagueMember, Notification

player_only = user_passes_test(lambda u: not u.is_staff, login_url='/admin/')

def auth_login(request):
    if request.user.is_authenticated: return redirect('index')
    error = None
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user:
            if user.is_staff: error = 'Administrators must log in via /admin/.'
            else:
                login(request, user)
                return redirect(request.GET.get('next', '/'))
        else: error = 'Invalid credentials.'
    return render(request, 'core/auth/login.html', {'error': error})

def auth_register(request):
    if request.user.is_authenticated: return redirect('index')
    error = None
    if request.method == 'POST':
        u, p, c = request.POST.get('username', '').strip(), request.POST.get('password', ''), request.POST.get('confirm', '')
        if not u or not p: error = 'All fields required.'
        elif p != c: error = 'Passwords do not match.'
        elif User.objects.filter(username=u).exists(): error = 'Username taken.'
        elif len(p) < 8: error = 'Password must be 8+ characters.'
        else:
            user = User.objects.create_user(username=u, password=p)
            login(request, user)
            return redirect('index')
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
            if prev_team: prev_points = prev_team.total_points

    context = {
        'num_teams': Team.objects.count(),
        'num_players': Player.objects.count(),
        'active_gameweek': active_gw,
        'recent_matches': Match.objects.filter(is_played=True).order_by('-gameweek__number', '-match_date')[:5],
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
    bank = 100.0
    free_transfers = 1
    
    if active_gw:
        ft = FantasyTeam.objects.filter(user=request.user, gameweek=active_gw).first()
        if not ft: ft = FantasyTeam.objects.filter(user=request.user).order_by("-gameweek__number").first()
        if ft:
            saved_formation = ft.formation
            bank = ft.bank
            free_transfers = ft.free_transfers
            for pick in ft.picks.all():
                existing_picks.append({
                    'id': pick.player.id,
                    'pos': pick.player.position,
                    'is_sub': pick.is_sub,
                    'purchase_price': pick.purchase_price or pick.player.price,
                    'is_captain': pick.is_captain,
                    'is_vice_captain': getattr(pick, 'is_vice_captain', False)
                })
                
    return render(request, 'core/pick_team.html', {
        'players': players, 'active_gameweek': active_gw, 'saved_picks_json': json.dumps(existing_picks),
        'saved_formation': saved_formation, 'bank': bank, 'free_transfers': free_transfers,
    })

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
    for i, r in enumerate(rankings): r['rank'] = i + 1
    return render(request, 'core/league_detail.html', {'league': league, 'rankings': rankings, 'is_member': request.user.is_authenticated and members.filter(user=request.user).exists()})

@login_required
def get_notifications(request):
    notifs = Notification.objects.filter(user=request.user).order_by('-created_at')[:15]
    return JsonResponse({'notifications': [{'id': n.id, 'message': n.message, 'is_read': n.is_read, 'date': n.created_at.strftime("%b %d, %H:%M")} for n in notifs]})

@csrf_exempt
@login_required
def mark_notifications_read(request):
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'ok': True})
    return JsonResponse({'error': 'POST required'}, status=405)

@login_required
def get_team_of_the_week(request):
    latest_match = Match.objects.filter(is_played=True).order_by('-gameweek__number').first()
    if not latest_match: return JsonResponse({'error': 'No matches played yet'})
    
    gw = latest_match.gameweek
    totw_players = []
    
    def get_top_players(pos, count):
        stats = PlayerStat.objects.filter(match__gameweek=gw, player__position=pos).order_by('-fantasy_points')[:count]
        for s in stats:
            totw_players.append({
                'id': s.player.id,  # RESTORED ID: Fixes the bug where clicking TOTW throws a 404 or loads wrong player
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
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            league = League.objects.create(name=name, created_by=request.user)
            LeagueMember.objects.create(league=league, user=request.user)
            return redirect('league_detail', code=league.code)
    return render(request, 'core/create_league.html')

@login_required
def join_league(request):
    if request.method == 'POST':
        code = request.POST.get('code')
        if code:
            league = get_object_or_404(League, code=code)
            LeagueMember.objects.get_or_create(league=league, user=request.user)
            return redirect('league_detail', code=league.code)
    return render(request, 'core/join_league.html')

@login_required
def leaderboard(request):
    user_leagues = LeagueMember.objects.filter(user=request.user).select_related('league')
    top_scorers = Player.objects.annotate(total_goals=Sum('stats__goals')).filter(total_goals__gt=0).order_by('-total_goals')[:5]
    top_assists = Player.objects.annotate(total_assists=Sum('stats__assists')).filter(total_assists__gt=0).order_by('-total_assists')[:5]
    top_points = Player.objects.annotate(total_pts=Sum('stats__fantasy_points')).filter(total_pts__gt=0).order_by('-total_pts')[:5]

    return render(request, 'core/leaderboard.html', {
        'user_leagues': user_leagues, 'top_scorers': top_scorers, 'top_assists': top_assists, 'top_points': top_points,
    })

@login_required
def user_profile(request):
    teams = FantasyTeam.objects.filter(user=request.user).order_by('gameweek__number')
    total_points = sum(t.total_points for t in teams)
    history_data = [{'gw': t.gameweek.number, 'pts': t.total_points} for t in teams]
    user_leagues = LeagueMember.objects.filter(user=request.user).select_related('league')
    return render(request, 'core/profile.html', {'total_points': total_points, 'history_data': history_data, 'user_leagues': user_leagues})

@login_required
def fixtures(request):
    from .models import Gameweek, Team, Match
    gameweeks = Gameweek.objects.prefetch_related('matches__home_team', 'matches__away_team').order_by('number')
    
    # Dynamically calculate the simulated Premier League Table
    teams_data = {t.id: {'name': t.name, 'short': t.short_name, 'played': 0, 'w': 0, 'd': 0, 'l': 0, 'gf': 0, 'ga': 0, 'gd': 0, 'pts': 0} for t in Team.objects.all()}
    
    played_matches = Match.objects.filter(is_played=True)
    for m in played_matches:
        h, a = m.home_team.id, m.away_team.id
        teams_data[h]['played'] += 1
        teams_data[a]['played'] += 1
        teams_data[h]['gf'] += m.home_score
        teams_data[h]['ga'] += m.away_score
        teams_data[a]['gf'] += m.away_score
        teams_data[a]['ga'] += m.home_score
        
        if m.home_score > m.away_score:
            teams_data[h]['w'] += 1
            teams_data[h]['pts'] += 3
            teams_data[a]['l'] += 1
        elif m.home_score < m.away_score:
            teams_data[a]['w'] += 1
            teams_data[a]['pts'] += 3
            teams_data[h]['l'] += 1
        else:
            teams_data[h]['d'] += 1
            teams_data[a]['d'] += 1
            teams_data[h]['pts'] += 1
            teams_data[a]['pts'] += 1
            
    for t in teams_data.values():
        t['gd'] = t['gf'] - t['ga']
        
    # Sort by Points, then Goal Difference, then Goals Scored
    standings = sorted(teams_data.values(), key=lambda x: (x['pts'], x['gd'], x['gf']), reverse=True)
    
    return render(request, 'core/fixtures.html', {'gameweeks': gameweeks, 'standings': standings})

@login_required
def get_player_detail(request, player_id):
    player = get_object_or_404(Player, id=player_id)
    stats = PlayerStat.objects.filter(player=player).select_related('match__gameweek', 'match__home_team', 'match__away_team').order_by('match__gameweek__number')
    
    history = []
    total_pts = 0
    for s in stats:
        opp = s.match.away_team.short_name if s.match.home_team == player.team else s.match.home_team.short_name
        history.append({'gw': s.match.gameweek.number, 'opp': opp, 'mins': s.minutes_played, 'pts': s.fantasy_points, 'goals': s.goals, 'assists': s.assists})
        total_pts += s.fantasy_points
        
    data = {'id': player.id, 'name': player.full_name, 'team': player.team.name, 'pos': player.position, 'price': float(player.price), 'total_pts': total_pts, 'history': history}
    return JsonResponse(data)

@csrf_exempt
@login_required
def save_picks(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            picks_data = data.get('picks', [])
            formation = data.get('formation', '433')
            
            active_gw = Gameweek.objects.filter(is_active=True).first()
            if not active_gw: return JsonResponse({'error': 'No active gameweek'})
                
            ft, created = FantasyTeam.objects.get_or_create(user=request.user, gameweek=active_gw)
            
            old_picks = {p.player.id: p for p in ft.picks.all()}
            new_ids = [int(p['player_id']) for p in picks_data]
            
            players_out = [p for pid, p in old_picks.items() if pid not in new_ids]
            players_in_data = [p for p in picks_data if int(p['player_id']) not in old_picks]
            
            if ft.picks.exists() and players_in_data:
                revenue = 0; cost = 0
                for old_pick in players_out:
                    pur_price = old_pick.purchase_price or old_pick.player.price
                    diff = float(old_pick.player.price) - float(pur_price)
                    sell_price = float(pur_price) + (math.floor(diff * 10) / 20.0) if diff > 0 else float(old_pick.player.price)
                    revenue += sell_price
                    
                for new_pick in players_in_data:
                    player = Player.objects.get(id=new_pick['player_id'])
                    cost += float(player.price)
                    
                net_cost = cost - revenue
                if float(ft.bank) - net_cost < -0.01: return JsonResponse({'error': f'Insufficient funds. You are short £{abs(float(ft.bank) - net_cost):.1f}m'})
                    
                transfers_made = len(players_in_data)
                if transfers_made > ft.free_transfers:
                    ft.points_hit += ((transfers_made - ft.free_transfers) * 4)
                    ft.free_transfers = 0
                else: ft.free_transfers -= transfers_made
                    
                ft.bank = float(ft.bank) - net_cost
            
            elif not ft.picks.exists():
                cost = sum(float(Player.objects.get(id=p['player_id']).price) for p in picks_data)
                if 100.0 - cost < -0.01: return JsonResponse({'error': 'Budget exceeded.'})
                ft.bank = 100.0 - cost

            ft.formation = formation; ft.save()
            ft.picks.all().delete()
            for p_data in picks_data:
                player = Player.objects.get(id=p_data['player_id'])
                old_pur = old_picks[player.id].purchase_price if player.id in old_picks else None
                FantasyPick.objects.create(fantasy_team=ft, player=player, is_captain=p_data.get('is_captain', False), is_vice_captain=p_data.get('is_vice_captain', False), is_sub=p_data.get('is_sub', False), purchase_price=old_pur or player.price)
                    
            return JsonResponse({'success': True, 'status': 'ok'})
        except Exception as e: return JsonResponse({'error': str(e)})
    return JsonResponse({'error': 'POST required'}, status=405)
