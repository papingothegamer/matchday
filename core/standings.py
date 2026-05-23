"""
MatchDay — Standings Computation Engine
========================================
These functions are called by the backend whenever a Tournament Admin
enters or updates match results. They demonstrate DATABASE AGGREGATION
and DENORMALIZATION patterns.

Each function is clearly commented for academic evaluation.
"""
from django.db.models import Sum, Count, Q
from .models import Tournament, TournamentTeam, Match, PlayerStat, Standing


# ═══════════════════════════════════════════════════════════════════════════════
# STANDINGS RECOMPUTATION
# ═══════════════════════════════════════════════════════════════════════════════

def recompute_standings(tournament):
    """
    ===== AGGREGATION FUNCTION: League Table Recomputation =====

    Called every time a Tournament Admin submits a match result.
    Iterates through ALL played matches in the tournament and tallies:
      - Wins (W), Draws (D), Losses (L)
      - Goals For (GF), Goals Against (GA)
      - Goal Difference (GD) = GF - GA
      - Points = (W × 3) + (D × 1)

    The results are saved into the Standing table (denormalized).
    This avoids recomputing on every page load — a classic optimization.
    """

    # Step 1: Get all teams registered in this tournament
    team_ids = TournamentTeam.objects.filter(
        tournament=tournament
    ).values_list('team_id', flat=True)

    # Step 2: Initialize empty stats for each team
    stats = {}
    for tid in team_ids:
        stats[tid] = {
            'played': 0, 'won': 0, 'drawn': 0, 'lost': 0,
            'goals_for': 0, 'goals_against': 0,
        }

    # Step 3: Iterate through all PLAYED matches and accumulate stats
    played_matches = Match.objects.filter(
        tournament=tournament,
        is_played=True
    )

    for match in played_matches:
        h_id = match.home_team_id
        a_id = match.away_team_id

        # Skip if teams aren't in our stats dict (safety check)
        if h_id not in stats or a_id not in stats:
            continue

        h_goals = match.home_score or 0
        a_goals = match.away_score or 0

        # Count matches played
        stats[h_id]['played'] += 1
        stats[a_id]['played'] += 1

        # Count goals for/against
        stats[h_id]['goals_for'] += h_goals
        stats[h_id]['goals_against'] += a_goals
        stats[a_id]['goals_for'] += a_goals
        stats[a_id]['goals_against'] += h_goals

        # Determine result: Win / Draw / Loss
        if h_goals > a_goals:
            # Home team wins
            stats[h_id]['won'] += 1
            stats[a_id]['lost'] += 1
        elif h_goals < a_goals:
            # Away team wins
            stats[a_id]['won'] += 1
            stats[h_id]['lost'] += 1
        else:
            # Draw
            stats[h_id]['drawn'] += 1
            stats[a_id]['drawn'] += 1

    # Step 4: Save computed standings to the database
    for tid, s in stats.items():
        gd = s['goals_for'] - s['goals_against']
        pts = (s['won'] * 3) + (s['drawn'] * 1)

        Standing.objects.update_or_create(
            tournament=tournament,
            team_id=tid,
            defaults={
                'played': s['played'],
                'won': s['won'],
                'drawn': s['drawn'],
                'lost': s['lost'],
                'goals_for': s['goals_for'],
                'goals_against': s['goals_against'],
                'goal_difference': gd,
                'points': pts,
            }
        )


# ═══════════════════════════════════════════════════════════════════════════════
# STATISTICS AGGREGATION QUERIES
# ═══════════════════════════════════════════════════════════════════════════════

def get_top_scorers(tournament, limit=10):
    """
    ===== AGGREGATION FUNCTION: Top Goal Scorers =====

    Uses Django ORM's annotate() + Sum() to aggregate goals across all
    matches in the tournament, grouped by player.

    SQL equivalent:
        SELECT player_id, SUM(goals) AS total_goals
        FROM core_playerstat
        WHERE match__tournament_id = ?
        GROUP BY player_id
        HAVING total_goals > 0
        ORDER BY total_goals DESC
        LIMIT 10
    """
    return PlayerStat.objects.filter(
        match__tournament=tournament
    ).values(
        'player__id', 'player__first_name', 'player__last_name',
        'player__team__name', 'player__team__short_name'
    ).annotate(
        total_goals=Sum('goals')
    ).filter(
        total_goals__gt=0
    ).order_by('-total_goals')[:limit]


def get_top_assists(tournament, limit=10):
    """
    ===== AGGREGATION FUNCTION: Top Assist Providers =====

    Same pattern as get_top_scorers but aggregates assists.
    """
    return PlayerStat.objects.filter(
        match__tournament=tournament
    ).values(
        'player__id', 'player__first_name', 'player__last_name',
        'player__team__name', 'player__team__short_name'
    ).annotate(
        total_assists=Sum('assists')
    ).filter(
        total_assists__gt=0
    ).order_by('-total_assists')[:limit]


def get_card_summary(tournament, limit=10):
    """
    ===== AGGREGATION FUNCTION: Disciplinary Record =====

    Aggregates yellow and red cards per player across the tournament.
    """
    return PlayerStat.objects.filter(
        match__tournament=tournament
    ).values(
        'player__id', 'player__first_name', 'player__last_name',
        'player__team__name', 'player__team__short_name'
    ).annotate(
        total_yellows=Sum('yellow_cards'),
        total_reds=Sum('red_cards')
    ).filter(
        Q(total_yellows__gt=0) | Q(total_reds__gt=0)
    ).order_by('-total_reds', '-total_yellows')[:limit]


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURE GENERATION ALGORITHMS
# ═══════════════════════════════════════════════════════════════════════════════

def generate_league_fixtures(tournament):
    from .models import Match as MatchModel

    teams = list(
        TournamentTeam.objects.filter(tournament=tournament)
        .select_related('team')
        .values_list('team', flat=True)
    )

    n = len(teams)
    if n < 2:
        return []

    if n % 2 == 1:
        teams.append(None)
        n += 1

    matches_created = []
    half = n // 2
    
    legs = getattr(tournament, 'league_legs', 1)

    for leg in range(legs):
        for matchday in range(n - 1):
            if legs > 1:
                round_label = f'Leg {leg + 1} - Matchday {matchday + 1}'
            else:
                round_label = f'Matchday {matchday + 1}'

            for i in range(half):
                home_id = teams[i]
                away_id = teams[n - 1 - i]

                if home_id is None or away_id is None:
                    continue
                    
                if leg % 2 == 1:
                    home_id, away_id = away_id, home_id

                match = MatchModel.objects.create(
                    tournament=tournament,
                    home_team_id=home_id,
                    away_team_id=away_id,
                    round_label=round_label,
                )
                matches_created.append(match)

            teams.insert(1, teams.pop())

    return matches_created


def generate_knockout_bracket(tournament):
    """
    ===== ALGORITHM: Knockout Bracket Generation =====

    Creates a bracket structure for 8, 4, or 2 teams.
    Supports: Quarter-Finals → Semi-Finals → Final.
    Teams are shuffled randomly for fair seeding.
    """
    import random as rng
    from .models import KnockoutRound, KnockoutFixture, Match as MatchModel

    team_ids = list(
        TournamentTeam.objects.filter(tournament=tournament)
        .values_list('team_id', flat=True)
    )

    n = len(team_ids)
    rng.shuffle(team_ids)

    # Determine rounds based on team count
    if n >= 8:
        rounds_config = [
            ('Quarter-Final', 1, team_ids[:8]),
        ]
    elif n >= 4:
        rounds_config = [
            ('Semi-Final', 1, team_ids[:4]),
        ]
    elif n >= 2:
        rounds_config = [
            ('Final', 1, team_ids[:2]),
        ]
    else:
        return

    # Build first round
    first_round_name, order, selected_teams = rounds_config[0]
    ko_round = KnockoutRound.objects.create(
        tournament=tournament,
        round_name=first_round_name,
        round_order=order
    )

    for i in range(0, len(selected_teams), 2):
        h_id = selected_teams[i]
        a_id = selected_teams[i + 1] if i + 1 < len(selected_teams) else None

        match = MatchModel.objects.create(
            tournament=tournament,
            home_team_id=h_id,
            away_team_id=a_id,
            round_label=first_round_name,
        )

        KnockoutFixture.objects.create(
            round=ko_round,
            match=match,
            home_team_id=h_id,
            away_team_id=a_id,
        )

    # Create placeholder rounds for subsequent stages
    if first_round_name == 'Quarter-Final':
        sf = KnockoutRound.objects.create(tournament=tournament, round_name='Semi-Final', round_order=2)
        for i in range(2):
            KnockoutFixture.objects.create(round=sf)
        final = KnockoutRound.objects.create(tournament=tournament, round_name='Final', round_order=3)
        KnockoutFixture.objects.create(round=final)
    elif first_round_name == 'Semi-Final':
        final = KnockoutRound.objects.create(tournament=tournament, round_name='Final', round_order=2)
        KnockoutFixture.objects.create(round=final)


def advance_knockout_winner(fixture):
    from .models import KnockoutFixture, Match as MatchModel

    if not fixture.match or not fixture.match.is_played:
        return
        
    if getattr(fixture, 'match_leg2', None) and not fixture.match_leg2.is_played:
        return

    is_golden_goal = getattr(fixture.round.tournament, 'ko_progression', 'SINGLE') == 'GOLDEN_GOAL'
    is_aggregate = getattr(fixture.round.tournament, 'ko_progression', 'SINGLE') == 'AGGREGATE'
    
    h_score = fixture.match.home_score
    a_score = fixture.match.away_score
    
    if is_aggregate and fixture.match_leg2:
        h_score += fixture.match_leg2.away_score
        a_score += fixture.match_leg2.home_score
        
    if h_score > a_score:
        winner = fixture.home_team
    elif a_score > h_score:
        winner = fixture.away_team
    else:
        winner = fixture.home_team

    fixture.winner = winner
    fixture.save()

    next_rounds = fixture.round.tournament.knockout_rounds.filter(
        round_order=fixture.round.round_order + 1
    )

    if not next_rounds.exists():
        return

    next_round = next_rounds.first()
    next_fixtures = list(next_round.fixtures.all().order_by('id'))

    current_fixtures = list(fixture.round.fixtures.all().order_by('id'))
    fixture_index = current_fixtures.index(fixture)
    next_fixture_index = fixture_index // 2

    if next_fixture_index < len(next_fixtures):
        nf = next_fixtures[next_fixture_index]
        if fixture_index % 2 == 0:
            nf.home_team = winner
        else:
            nf.away_team = winner
        nf.save()
        
        if nf.home_team and nf.away_team and not nf.match:
            is_agg = getattr(fixture.round.tournament, 'ko_progression', 'SINGLE') == 'AGGREGATE'
            nf.match = MatchModel.objects.create(
                tournament=fixture.round.tournament,
                home_team_id=nf.home_team.id,
                away_team_id=nf.away_team.id,
                round_label=f"{nf.round.round_name} (Leg 1)" if (is_agg and nf.round.round_name != 'Final') else nf.round.round_name,
            )
            if is_agg and nf.round.round_name != 'Final':
                nf.match_leg2 = MatchModel.objects.create(
                    tournament=fixture.round.tournament,
                    home_team_id=nf.away_team.id,
                    away_team_id=nf.home_team.id,
                    round_label=f"{nf.round.round_name} (Leg 2)",
                )
            nf.save()
