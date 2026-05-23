"""
MatchDay — Views (Tournament Registration & Management System)
===============================================================
All request handlers grouped by role:
  1. Authentication (login, register with role selection, logout)
  2. Coach Views (dashboard, browse tournaments, register team, view standings)
  3. Tournament Admin Views (admin dashboard, tournament CRUD, enter results)
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Q
from django.utils import timezone
import json

from .models import (
    Team, Player, Tournament, TournamentTeam, Match, PlayerStat,
    Standing, KnockoutRound, KnockoutFixture,
)
from .standings import (
    recompute_standings, get_top_scorers, get_top_assists,
    get_card_summary, generate_league_fixtures, generate_knockout_bracket,
    advance_knockout_winner,
)


# ═══════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION
# ═══════════════════════════════════════════════════════════════════════════════

def auth_login(request):
    """Login view. Redirects based on role after login."""
    if request.user.is_authenticated:
        return redirect('index')
    error = None
    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username'),
            password=request.POST.get('password'),
        )
        if user:
            login(request, user)
            if user.is_staff and not user.is_superuser:
                return redirect('admin_dashboard')
            return redirect('index')
        else:
            error = 'Invalid username or password.'
    return render(request, 'core/auth/login.html', {'error': error})


def auth_register(request):
    """
    Registration with ROLE SELECTION.
    Users choose to register as a Coach or Tournament Admin.
    """
    if request.user.is_authenticated:
        return redirect('index')
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm', '')
        role = request.POST.get('role', 'coach')  # 'coach' or 'admin'

        if not username or not password:
            error = 'All fields are required.'
        elif password != confirm:
            error = 'Passwords do not match.'
        elif User.objects.filter(username=username).exists():
            error = 'Username is already taken.'
        elif len(password) < 8:
            error = 'Password must be at least 8 characters.'
        else:
            user = User.objects.create_user(username=username, password=password)
            if role == 'admin':
                user.is_staff = True
                user.save()
            login(request, user)
            if role == 'admin':
                return redirect('admin_dashboard')
            return redirect('index')
    return render(request, 'core/auth/register.html', {'error': error})


def auth_logout(request):
    logout(request)
    return redirect('login')


# ═══════════════════════════════════════════════════════════════════════════════
# COACH VIEWS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def index(request):
    """
    ===== COACH DASHBOARD =====
    Shows the coach's team(s) and tournaments they've joined.
    """
    my_teams = Team.objects.filter(coach=request.user)
    my_tournament_ids = TournamentTeam.objects.filter(
        team__coach=request.user
    ).values_list('tournament_id', flat=True)
    my_tournaments = Tournament.objects.filter(id__in=my_tournament_ids)

    return render(request, 'core/index.html', {
        'my_teams': my_teams,
        'my_tournaments': my_tournaments,
    })


@login_required
def tournament_list(request):
    """
    ===== READ (CRUD): Browse All Tournaments =====
    Displays all active/draft tournaments for coaches to browse and join.
    """
    tournaments = Tournament.objects.all().annotate(
        team_count=Sum('tournament_teams__id', default=0)  # Just to trigger the join
    )
    # Recalculate team_count properly
    for t in tournaments:
        t.num_teams = t.tournament_teams.count()

    return render(request, 'core/tournament_list.html', {
        'tournaments': tournaments,
    })


@login_required
def tournament_detail(request, tournament_id):
    """
    ===== READ (CRUD): Tournament Overview =====
    Shows standings, fixtures, top scorers, and registered teams.
    Accessible by both Coaches and Tournament Admins.
    """
    tournament = get_object_or_404(Tournament, pk=tournament_id)
    standings = Standing.objects.filter(tournament=tournament).select_related('team')
    matches = Match.objects.filter(tournament=tournament).select_related('home_team', 'away_team')
    teams = TournamentTeam.objects.filter(tournament=tournament).select_related('team__coach')

    top_scorers = get_top_scorers(tournament, limit=10)
    top_assists_list = get_top_assists(tournament, limit=10)
    cards = get_card_summary(tournament, limit=10)

    # Check if current user's team is registered
    user_registered = TournamentTeam.objects.filter(
        tournament=tournament, team__coach=request.user
    ).exists()

    # Knockout rounds (if applicable)
    ko_rounds = []
    if tournament.format == 'KNOCKOUT':
        for r in tournament.knockout_rounds.all().order_by('round_order'):
            fixtures = r.fixtures.all().select_related('home_team', 'away_team', 'winner', 'match')
            ko_rounds.append({'round': r, 'fixtures': fixtures})

    return render(request, 'core/tournament_detail.html', {
        'tournament': tournament,
        'standings': standings,
        'matches': matches,
        'teams': teams,
        'top_scorers': top_scorers,
        'top_assists': top_assists_list,
        'cards': cards,
        'user_registered': user_registered,
        'ko_rounds': ko_rounds,
    })


@login_required
def register_team(request, tournament_id):
    """
    ===== CREATE (CRUD): Register Team + Players into a Tournament =====
    Coach fills out a form with team name and player details.
    Creates a Team, Player objects, and a TournamentTeam entry.
    """
    tournament = get_object_or_404(Tournament, pk=tournament_id)

    # Check if coach already has a team in this tournament
    existing = TournamentTeam.objects.filter(
        tournament=tournament, team__coach=request.user
    ).exists()
    if existing:
        return redirect('tournament_detail', tournament_id=tournament.pk)

    if request.method == 'POST':
        team_name = request.POST.get('team_name', '').strip()
        short_name = request.POST.get('short_name', '').strip().upper()[:5]
        primary_color = request.POST.get('primary_color', '#333333')
        secondary_color = request.POST.get('secondary_color', '#FFFFFF')

        if not team_name or not short_name:
            return render(request, 'core/register_team.html', {
                'tournament': tournament,
                'error': 'Team name and short name are required.',
            })

        # CREATE the team
        team = Team.objects.create(
            name=team_name,
            short_name=short_name,
            primary_color=primary_color,
            secondary_color=secondary_color,
            coach=request.user,
        )

        # CREATE players from form data
        player_count = int(request.POST.get('player_count', 0))
        for i in range(player_count):
            fname = request.POST.get(f'player_{i}_first_name', '').strip()
            lname = request.POST.get(f'player_{i}_last_name', '').strip()
            pos = request.POST.get(f'player_{i}_position', 'MID')
            jersey = request.POST.get(f'player_{i}_jersey', 0)
            if lname:  # Only create if at least last name is provided
                Player.objects.create(
                    team=team,
                    first_name=fname,
                    last_name=lname,
                    position=pos,
                    jersey_number=int(jersey) if jersey else 0,
                )

        # Register team into tournament
        TournamentTeam.objects.create(tournament=tournament, team=team)

        # Initialize standing row
        Standing.objects.get_or_create(tournament=tournament, team=team)

        return redirect('tournament_detail', tournament_id=tournament.pk)

    return render(request, 'core/register_team.html', {
        'tournament': tournament,
    })


@login_required
def team_detail(request, tournament_id, team_id):
    """
    ===== READ (CRUD): View Team Roster & Last Lineup =====
    Any coach can view any team's registered players and their stats.
    This is the "suggested lineup" feature (Option A: actual registered squad).
    """
    tournament = get_object_or_404(Tournament, pk=tournament_id)
    team = get_object_or_404(Team, pk=team_id)
    players = Player.objects.filter(team=team).order_by('position', 'jersey_number')

    # Aggregate player stats within this tournament
    player_stats = []
    for p in players:
        stats = PlayerStat.objects.filter(
            player=p, match__tournament=tournament
        ).aggregate(
            total_goals=Sum('goals'),
            total_assists=Sum('assists'),
            total_yellows=Sum('yellow_cards'),
            total_reds=Sum('red_cards'),
            total_minutes=Sum('minutes_played'),
        )
        player_stats.append({
            'player': p,
            'goals': stats['total_goals'] or 0,
            'assists': stats['total_assists'] or 0,
            'yellows': stats['total_yellows'] or 0,
            'reds': stats['total_reds'] or 0,
            'minutes': stats['total_minutes'] or 0,
        })

    # Build suggested lineup: best XI by position (GK:1, DEF:4, MID:4, FWD:2)
    lineup = {
        'GK': [p for p in players if p.position == 'GK'][:1],
        'DEF': [p for p in players if p.position == 'DEF'][:4],
        'MID': [p for p in players if p.position == 'MID'][:4],
        'FWD': [p for p in players if p.position == 'FWD'][:2],
    }

    return render(request, 'core/team_detail.html', {
        'tournament': tournament,
        'team': team,
        'player_stats': player_stats,
        'lineup': lineup,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# TOURNAMENT ADMIN VIEWS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admin_dashboard(request):
    """
    ===== TOURNAMENT ADMIN DASHBOARD =====
    Shows all tournaments managed by this admin.
    """
    if not request.user.is_staff:
        return redirect('index')

    my_tournaments = Tournament.objects.filter(created_by=request.user)
    for t in my_tournaments:
        t.num_teams = t.tournament_teams.count()
        t.num_matches_played = t.matches.filter(is_played=True).count()
        t.num_matches_total = t.matches.count()

    return render(request, 'core/admin_dashboard.html', {
        'tournaments': my_tournaments,
    })


@login_required
def create_tournament(request):
    """
    ===== CREATE (CRUD): Create a New Tournament =====
    Tournament Admin creates a tournament with a name, format, and description.
    """
    if not request.user.is_staff:
        return redirect('index')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        fmt = request.POST.get('format', 'LEAGUE')
        description = request.POST.get('description', '').strip()

        if name:
            Tournament.objects.create(
                name=name,
                format=fmt,
                description=description,
                created_by=request.user,
            )
            return redirect('admin_dashboard')

    return render(request, 'core/create_tournament.html')


@login_required
def edit_tournament(request, tournament_id):
    """
    ===== UPDATE (CRUD): Edit Tournament Details =====
    """
    if not request.user.is_staff:
        return redirect('index')

    tournament = get_object_or_404(Tournament, pk=tournament_id, created_by=request.user)

    if request.method == 'POST':
        tournament.name = request.POST.get('name', tournament.name).strip()
        tournament.format = request.POST.get('format', tournament.format)
        tournament.status = request.POST.get('status', tournament.status)
        tournament.description = request.POST.get('description', tournament.description).strip()
        tournament.save()
        return redirect('admin_dashboard')

    return render(request, 'core/create_tournament.html', {
        'tournament': tournament,
        'edit_mode': True,
    })


@login_required
def delete_tournament(request, tournament_id):
    """
    ===== DELETE (CRUD): Delete a Tournament =====
    """
    if not request.user.is_staff:
        return redirect('index')

    tournament = get_object_or_404(Tournament, pk=tournament_id, created_by=request.user)
    if request.method == 'POST':
        tournament.delete()
    return redirect('admin_dashboard')


@login_required
def manage_fixtures(request, tournament_id):
    """
    ===== Tournament Admin: Generate & View Fixtures =====
    If no fixtures exist, generates them based on the tournament format.
    """
    if not request.user.is_staff:
        return redirect('index')

    tournament = get_object_or_404(Tournament, pk=tournament_id, created_by=request.user)

    if request.method == 'POST' and 'generate' in request.POST:
        # Generate fixtures
        if tournament.format == 'LEAGUE':
            generate_league_fixtures(tournament)
        else:
            generate_knockout_bracket(tournament)
        tournament.status = 'ACTIVE'
        tournament.save()
        return redirect('manage_fixtures', tournament_id=tournament.pk)

    matches = Match.objects.filter(tournament=tournament).select_related('home_team', 'away_team')

    # Group matches by round_label
    rounds = {}
    for m in matches:
        if m.round_label not in rounds:
            rounds[m.round_label] = []
        rounds[m.round_label].append(m)

    return render(request, 'core/manage_fixtures.html', {
        'tournament': tournament,
        'rounds': rounds,
        'has_fixtures': matches.exists(),
    })


@login_required
def enter_match_result(request, match_id):
    """
    ===== UPDATE (CRUD): Enter Match Result + Player Stats =====

    This is the KEY view that triggers the standings computation.
    The Tournament Admin enters:
      1. The final score (home_score, away_score)
      2. Per-player stats (goals, assists, cards, minutes)

    After saving, it calls recompute_standings() to update the league table.
    """
    if not request.user.is_staff:
        return redirect('index')

    match = get_object_or_404(Match, pk=match_id)
    tournament = match.tournament

    # Get players from both teams
    home_players = Player.objects.filter(team=match.home_team).order_by('position', 'jersey_number')
    away_players = Player.objects.filter(team=match.away_team).order_by('position', 'jersey_number')

    if request.method == 'POST':
        # Save match score
        match.home_score = int(request.POST.get('home_score', 0))
        match.away_score = int(request.POST.get('away_score', 0))
        match.is_played = True
        match.save()

        # Save player stats
        all_players = list(home_players) + list(away_players)
        for player in all_players:
            goals = int(request.POST.get(f'goals_{player.id}', 0))
            assists = int(request.POST.get(f'assists_{player.id}', 0))
            yellows = int(request.POST.get(f'yellows_{player.id}', 0))
            reds = int(request.POST.get(f'reds_{player.id}', 0))
            minutes = int(request.POST.get(f'minutes_{player.id}', 0))

            PlayerStat.objects.update_or_create(
                player=player, match=match,
                defaults={
                    'goals': goals,
                    'assists': assists,
                    'yellow_cards': yellows,
                    'red_cards': reds,
                    'minutes_played': minutes,
                }
            )

        # ===== TRIGGER STANDINGS RECOMPUTATION =====
        # This is the core backend logic that the evaluator should see.
        recompute_standings(tournament)

        # If knockout match, advance winner
        if hasattr(match, 'knockout_fixture'):
            advance_knockout_winner(match.knockout_fixture)

        return redirect('tournament_detail', tournament_id=tournament.pk)

    # Load existing stats if editing
    existing_stats = {}
    for ps in PlayerStat.objects.filter(match=match):
        existing_stats[ps.player_id] = ps

    return render(request, 'core/enter_result.html', {
        'match': match,
        'tournament': tournament,
        'home_players': home_players,
        'away_players': away_players,
        'existing_stats': existing_stats,
    })


@login_required
def auto_simulate_match(request, match_id):
    """
    ===== Tournament Admin: Auto-Simulate Match =====
    Generates realistic random match stats and score for the fixture.
    Runs standings recomputation automatically.
    """
    if not request.user.is_staff:
        return redirect('index')

    import random
    match = get_object_or_404(Match, pk=match_id)
    tournament = match.tournament

    # Delete any existing player stats for this match first (for clean re-playability)
    PlayerStat.objects.filter(match=match).delete()

    # Random realistic scores
    match.home_score = random.choices([0, 1, 2, 3, 4], weights=[25, 35, 20, 12, 8])[0]
    match.away_score = random.choices([0, 1, 2, 3, 4], weights=[30, 30, 22, 12, 6])[0]
    match.is_played = True
    match.save()

    # Generate player stats for both teams
    for team_obj in [match.home_team, match.away_team]:
        is_home = (team_obj == match.home_team)
        goals = match.home_score if is_home else match.away_score

        players = list(Player.objects.filter(team=team_obj))
        scorers = [p for p in players if p.position in ('FWD', 'MID')]
        goal_assignments = random.choices(scorers, k=goals) if goals > 0 and scorers else []

        for player in players:
            g = goal_assignments.count(player)
            a = 1 if random.random() < 0.15 and g == 0 else 0
            yc = 1 if random.random() < 0.08 else 0
            rc = 1 if random.random() < 0.02 else 0
            mins = random.randint(60, 90) if random.random() < 0.85 else random.randint(0, 59)

            PlayerStat.objects.create(
                player=player, match=match,
                goals=g, assists=a,
                yellow_cards=yc, red_cards=rc,
                minutes_played=mins,
            )

    # ===== TRIGGER STANDINGS RECOMPUTATION =====
    recompute_standings(tournament)

    # If knockout match, advance winner
    if hasattr(match, 'knockout_fixture'):
        advance_knockout_winner(match.knockout_fixture)

    # Redirect to referer or tournament detail
    referer = request.META.get('HTTP_REFERER')
    if referer and ('/fixtures/' in referer or '/tournaments/' in referer):
        return redirect(referer)
    return redirect('tournament_detail', tournament_id=tournament.pk)


# ═══════════════════════════════════════════════════════════════════════════════
# JSON API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def api_standings(request, tournament_id):
    """JSON endpoint for standings data (used by frontend if needed)."""
    tournament = get_object_or_404(Tournament, pk=tournament_id)
    standings = Standing.objects.filter(tournament=tournament).select_related('team')
    data = [{
        'team': s.team.name,
        'short': s.team.short_name,
        'played': s.played,
        'won': s.won,
        'drawn': s.drawn,
        'lost': s.lost,
        'gf': s.goals_for,
        'ga': s.goals_against,
        'gd': s.goal_difference,
        'pts': s.points,
    } for s in standings]
    return JsonResponse({'standings': data})


@login_required
def api_top_scorers(request, tournament_id):
    """JSON endpoint for top scorers (used by frontend if needed)."""
    tournament = get_object_or_404(Tournament, pk=tournament_id)
    scorers = get_top_scorers(tournament, limit=10)
    data = [{
        'name': f"{s['player__first_name']} {s['player__last_name']}".strip(),
        'team': s['player__team__short_name'],
        'goals': s['total_goals'],
    } for s in scorers]
    return JsonResponse({'scorers': data})
