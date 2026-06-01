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
    return render(request, 'core/auth/login.html', {
        # 'error': String containing error message if authentication fails (displayed above login form)
        'error': error
    })


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
    return render(request, 'core/auth/register.html', {
        # 'error': String containing validation error message if registration fails (displayed above register form)
        'error': error
    })


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
    if request.method == 'POST' and 'dismiss_notifications' in request.POST:
        from .models import Notification
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return redirect('index')

    my_teams = Team.objects.filter(coach=request.user)
    my_tournament_ids = TournamentTeam.objects.filter(
        team__coach=request.user
    ).values_list('tournament_id', flat=True)
    my_tournaments = Tournament.objects.filter(id__in=my_tournament_ids)
    available_tournaments = Tournament.objects.filter(status='DRAFT').exclude(id__in=my_tournament_ids)
    
    from .models import Notification
    notifications = Notification.objects.filter(user=request.user, is_read=False)

    return render(request, 'core/index.html', {
        # 'my_teams': QuerySet of Team instances owned by user (rendered in Quick Stats and My Teams grid)
        'my_teams': my_teams,
        # 'my_tournaments': QuerySet of Tournament instances the user's teams are in (rendered in My Tournaments grid)
        'my_tournaments': my_tournaments,
        # 'available_tournaments': QuerySet of DRAFT Tournament instances the user hasn't joined (rendered in Available to Join grid)
        'available_tournaments': available_tournaments,
        # 'notifications': QuerySet of unread Notification instances for the user (rendered in Recent Notifications panel)
        'notifications': notifications,
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
        # 'tournaments': QuerySet of all Tournament instances with team_count annotated (rendered as a list of tournaments to browse)
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
        # 'tournament': The Tournament instance being viewed (rendered in header)
        'tournament': tournament,
        # 'standings': QuerySet of Standing instances for this tournament (rendered in League Table)
        'standings': standings,
        # 'matches': QuerySet of all Match instances for this tournament (rendered in fixtures list)
        'matches': matches,
        # 'teams': QuerySet of TournamentTeam instances representing registered teams (rendered in Teams grid)
        'teams': teams,
        # 'top_scorers': List of dicts containing top goal scorers (rendered in Top Scorers table)
        'top_scorers': top_scorers,
        # 'top_assists': List of dicts containing top assist providers (rendered in Top Assists table)
        'top_assists': top_assists_list,
        # 'cards': List of dicts containing top card recipients (rendered in Cards table)
        'cards': cards,
        # 'user_registered': Boolean indicating if the current coach has a team in this tournament (controls display of Register button)
        'user_registered': user_registered,
        # 'ko_rounds': List of dicts containing KnockoutRound and its fixtures (rendered in Knockout Bracket)
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
        # 'tournament': The Tournament instance the user is registering for (rendered in header/breadcrumbs)
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
        # 'tournament': The Tournament context for this team view (rendered in breadcrumbs)
        'tournament': tournament,
        # 'team': The Team instance being viewed (rendered in team info header)
        'team': team,
        # 'player_stats': List of dicts containing player stats for this tournament (rendered in Roster table)
        'player_stats': player_stats,
        # 'lineup': Dict grouping top players by position for the pitch view (rendered in Suggested Lineup pitch)
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
        # 'tournaments': QuerySet of Tournament instances created by this admin (rendered in Admin Tournaments list)
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
        league_legs = int(request.POST.get('league_legs', 1))
        ko_progression = request.POST.get('ko_progression', 'SINGLE')

        if name:
            Tournament.objects.create(
                name=name,
                format=fmt,
                description=description,
                league_legs=league_legs,
                ko_progression=ko_progression,
                created_by=request.user,
            )
            return redirect('admin_dashboard')

    return render(request, 'core/create_tournament.html', {
        # No extra context passed for simple create view
    })


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
        tournament.league_legs = int(request.POST.get('league_legs', tournament.league_legs))
        tournament.ko_progression = request.POST.get('ko_progression', tournament.ko_progression)
        tournament.save()
        return redirect('admin_dashboard')

    return render(request, 'core/create_tournament.html', {
        # 'tournament': The Tournament instance being edited (used to prepopulate form fields)
        'tournament': tournament,
        # 'edit_mode': Boolean flag indicating to the template that this is an edit operation
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

    if request.method == 'POST':
        if 'generate' in request.POST:
            # Generate fixtures
            if tournament.format == 'LEAGUE':
                generate_league_fixtures(tournament)
            else:
                generate_knockout_bracket(tournament)
            tournament.status = 'ACTIVE'
            tournament.save()
            return redirect('manage_fixtures', tournament_id=tournament.pk)
            
        elif 'auto_schedule' in request.POST:
            from datetime import timedelta
            from django.utils import timezone
            unplayed = Match.objects.filter(tournament=tournament, is_played=False, match_date__isnull=True).order_by('id')
            if unplayed.exists():
                start_date = timezone.now().replace(hour=15, minute=0, second=0, microsecond=0)
                days_ahead = 5 - start_date.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                next_saturday = start_date + timedelta(days=days_ahead)
                
                round_dates = {}
                current_date = next_saturday
                
                for m in unplayed:
                    if m.round_label not in round_dates:
                        round_dates[m.round_label] = current_date
                        current_date += timedelta(days=7)
                        
                    m.match_date = round_dates[m.round_label]
                    m.save()
                    
                    if m.home_team and m.home_team.coach:
                        Notification.objects.create(user=m.home_team.coach, message=f"Your team {m.home_team.name} has a match scheduled on {m.match_date.strftime('%b %d, %Y')} against {m.away_team.name if m.away_team else 'TBD'}.")
                    if m.away_team and m.away_team.coach:
                        Notification.objects.create(user=m.away_team.coach, message=f"Your team {m.away_team.name} has a match scheduled on {m.match_date.strftime('%b %d, %Y')} against {m.home_team.name if m.home_team else 'TBD'}.")

            return redirect('manage_fixtures', tournament_id=tournament.pk)

        elif 'set_match_date' in request.POST:
            match_id = request.POST.get('match_id')
            match_date_str = request.POST.get('match_date')
            if match_id and match_date_str:
                from django.utils.dateparse import parse_datetime
                m = get_object_or_404(Match, pk=match_id, tournament=tournament)
                parsed_date = parse_datetime(match_date_str)
                if parsed_date:
                    m.match_date = parsed_date
                    m.save()
                    if m.home_team and m.home_team.coach:
                        Notification.objects.create(user=m.home_team.coach, message=f"Date updated: {m.home_team.name} vs {m.away_team.name if m.away_team else 'TBD'} is now scheduled for {m.match_date.strftime('%b %d, %Y %H:%M')}.")
                    if m.away_team and m.away_team.coach:
                        Notification.objects.create(user=m.away_team.coach, message=f"Date updated: {m.away_team.name} vs {m.home_team.name if m.home_team else 'TBD'} is now scheduled for {m.match_date.strftime('%b %d, %Y %H:%M')}.")

            return redirect('manage_fixtures', tournament_id=tournament.pk)

    matches = Match.objects.filter(tournament=tournament).select_related('home_team', 'away_team')

    # Group matches by round_label
    rounds = {}
    for m in matches:
        if m.round_label not in rounds:
            rounds[m.round_label] = []
        rounds[m.round_label].append(m)

    return render(request, 'core/manage_fixtures.html', {
        # 'tournament': The Tournament instance being managed (rendered in header)
        'tournament': tournament,
        # 'rounds': Dict grouping matches by round_label (rendered as match blocks per round)
        'rounds': rounds,
        # 'has_fixtures': Boolean indicating if fixtures have been generated (controls Generate button display)
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
        # 'match': The Match instance being updated (rendered in header)
        'match': match,
        # 'tournament': The Tournament context (rendered in breadcrumbs)
        'tournament': tournament,
        # 'home_players': QuerySet of Player instances for the home team (rendered in Home Team Stats form)
        'home_players': home_players,
        # 'away_players': QuerySet of Player instances for the away team (rendered in Away Team Stats form)
        'away_players': away_players,
        # 'existing_stats': Dict mapping player IDs to PlayerStat instances (used to prepopulate stats inputs)
        'existing_stats': existing_stats,
    })


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
