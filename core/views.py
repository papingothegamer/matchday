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
                'purchase_price': pick.purchase_price,
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

@login_required
def leaderboard(request):
    from django.db.models import Sum
    from .models import FantasyTeam, LeagueMember, Player
    
    # Get user's leagues
    user_leagues = LeagueMember.objects.filter(user=request.user).select_related('league')
    
    # Calculate Simulation Engine Stats dynamically
    top_scorers = Player.objects.annotate(total_goals=Sum('stats__goals')).filter(total_goals__gt=0).order_by('-total_goals')[:5]
    top_assists = Player.objects.annotate(total_assists=Sum('stats__assists')).filter(total_assists__gt=0).order_by('-total_assists')[:5]
    top_points = Player.objects.annotate(total_pts=Sum('stats__fantasy_points')).filter(total_pts__gt=0).order_by('-total_pts')[:5]

    context = {
        'user_leagues': user_leagues,
        'top_scorers': top_scorers,
        'top_assists': top_assists,
        'top_points': top_points,
    }
    return render(request, 'core/leaderboard.html', context)


@login_required
def user_profile(request):
    from .models import FantasyTeam, LeagueMember
    
    # Fetch user's team history ordered by gameweek
    teams = FantasyTeam.objects.filter(user=request.user).order_by('gameweek__number')
    
    # Calculate lifetime points
    total_points = sum(t.total_points for t in teams)
    
    # Prepare data for the JS Bar Chart
    history_data = [{'gw': t.gameweek.number, 'pts': t.total_points} for t in teams]
    
    # Fetch active leagues
    user_leagues = LeagueMember.objects.filter(user=request.user).select_related('league')
    
    context = {
        'total_points': total_points,
        'history_data': history_data,
        'user_leagues': user_leagues,
    }
    return render(request, 'core/profile.html', context)


@csrf_exempt
@login_required
def save_picks(request):
    import json, math
    from django.http import JsonResponse
    from .models import Gameweek, FantasyTeam, Player, FantasyPick, Transfer
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            picks_data = data.get('picks', [])
            formation = data.get('formation', '433')
            
            active_gw = Gameweek.objects.filter(is_active=True).first()
            if not active_gw:
                return JsonResponse({'error': 'No active gameweek'})
                
            ft, created = FantasyTeam.objects.get_or_create(user=request.user, gameweek=active_gw)
            
            # Map current players before the change
            old_picks = {p.player.id: p for p in ft.picks.all()}
            new_ids = [int(p['player_id']) for p in picks_data]
            
            players_out = [p for pid, p in old_picks.items() if pid not in new_ids]
            players_in_data = [p for p in picks_data if int(p['player_id']) not in old_picks]
            
            # If the user already has a team and is making transfers
            if ft.picks.exists() and players_in_data:
                revenue = 0
                cost = 0
                
                # Calculate Revenue with 50% Profit Tax
                for old_pick in players_out:
                    diff = old_pick.player.price - old_pick.purchase_price
                    if diff > 0:
                        sell_price = old_pick.purchase_price + (math.floor(diff * 10) / 20.0)
                    else:
                        sell_price = old_pick.player.price
                    revenue += sell_price
                    
                # Calculate Cost
                for new_pick in players_in_data:
                    player = Player.objects.get(id=new_pick['player_id'])
                    cost += player.price
                    
                net_cost = cost - revenue
                if ft.bank - net_cost < 0:
                    return JsonResponse({'error': f'Insufficient funds. You are short £{abs(ft.bank - net_cost):.1f}m'})
                    
                # Deduct Free Transfers & Apply Hits
                transfers_made = len(players_in_data)
                if transfers_made > ft.free_transfers:
                    extra = transfers_made - ft.free_transfers
                    ft.points_hit += (extra * 4) # -4 points per extra transfer
                    ft.free_transfers = 0
                else:
                    ft.free_transfers -= transfers_made
                    
                ft.bank -= net_cost
                
                # Log the transactions
                for out_p, in_p in zip(players_out, players_in_data):
                    in_player = Player.objects.get(id=in_p['player_id'])
                    Transfer.objects.create(
                        user=request.user, gameweek=active_gw,
                        player_out=out_p.player, player_in=in_player
                    )
            
            # First time drafting (Unlimited free transfers)
            elif not ft.picks.exists():
                cost = sum(Player.objects.get(id=p['player_id']).price for p in picks_data)
                if 100.0 - cost < 0:
                    return JsonResponse({'error': 'Budget exceeded.'})
                ft.bank = 100.0 - cost

            ft.formation = formation
            ft.save()
            
            # Rebuild the squad
            ft.picks.all().delete()
            for p_data in picks_data:
                player = Player.objects.get(id=p_data['player_id'])
                # Retain old purchase price if they already owned the player
                pur_price = old_picks[player.id].purchase_price if player.id in old_picks else player.price
                FantasyPick.objects.create(
                    fantasy_team=ft, player=player,
                    is_captain=p_data.get('is_captain', False),
                    is_sub=p_data.get('is_sub', False),
                    purchase_price=pur_price
                )
                    
            return JsonResponse({'success': True, 'status': 'ok'})
        except Exception as e:
            return JsonResponse({'error': str(e)})
            
    return JsonResponse({'error': 'POST required'}, status=405)
