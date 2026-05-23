import re

with open("core/standings.py", "r") as f:
    content = f.read()

# Replace generate_league_fixtures
new_league = """def generate_league_fixtures(tournament):
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

    return matches_created"""

content = re.sub(r'def generate_league_fixtures\(tournament\):.*?return matches_created', new_league, content, flags=re.DOTALL)


# Replace generate_knockout_bracket
new_ko = """def generate_knockout_bracket(tournament):
    import random as rng
    from .models import KnockoutRound, KnockoutFixture, Match as MatchModel

    team_ids = list(
        TournamentTeam.objects.filter(tournament=tournament)
        .values_list('team_id', flat=True)
    )

    n = len(team_ids)
    if n not in [2, 4, 8, 16]:
        return False

    rng.shuffle(team_ids)
    
    rounds_config = []
    if n == 16:
        rounds_config = [('Round of 16', 1)]
    elif n == 8:
        rounds_config = [('Quarter-Final', 1)]
    elif n == 4:
        rounds_config = [('Semi-Final', 1)]
    elif n == 2:
        rounds_config = [('Final', 1)]

    first_round_name, order = rounds_config[0]
    ko_round = KnockoutRound.objects.create(
        tournament=tournament,
        round_name=first_round_name,
        round_order=order
    )

    is_aggregate = getattr(tournament, 'ko_progression', 'SINGLE') == 'AGGREGATE'

    for i in range(0, n, 2):
        h_id = team_ids[i]
        a_id = team_ids[i + 1]

        match_leg1 = MatchModel.objects.create(
            tournament=tournament,
            home_team_id=h_id,
            away_team_id=a_id,
            round_label=f"{first_round_name} (Leg 1)" if (is_aggregate and first_round_name != 'Final') else first_round_name,
        )
        
        match_leg2 = None
        if is_aggregate and first_round_name != 'Final':
            match_leg2 = MatchModel.objects.create(
                tournament=tournament,
                home_team_id=a_id,
                away_team_id=h_id,
                round_label=f"{first_round_name} (Leg 2)",
            )

        KnockoutFixture.objects.create(
            round=ko_round,
            match=match_leg1,
            match_leg2=match_leg2,
            home_team_id=h_id,
            away_team_id=a_id,
        )

    current_round_name = first_round_name
    current_order = order
    while current_round_name != 'Final':
        current_order += 1
        if current_round_name == 'Round of 16':
            next_name = 'Quarter-Final'
            num_fixtures = 4
        elif current_round_name == 'Quarter-Final':
            next_name = 'Semi-Final'
            num_fixtures = 2
        elif current_round_name == 'Semi-Final':
            next_name = 'Final'
            num_fixtures = 1
            
        r = KnockoutRound.objects.create(tournament=tournament, round_name=next_name, round_order=current_order)
        for i in range(num_fixtures):
            KnockoutFixture.objects.create(round=r)
            
        current_round_name = next_name
        
    return True"""

content = re.sub(r'def generate_knockout_bracket\(tournament\):.*?elif first_round_name == \'Semi-Final\':[^d]*?KnockoutFixture\.objects\.create\(round=final\)', new_ko, content, flags=re.DOTALL)


# Replace advance_knockout_winner
new_adv = """def advance_knockout_winner(fixture):
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
            nf.save()"""

content = re.sub(r'def advance_knockout_winner\(fixture\):.*?nf\.save\(\)', new_adv, content, flags=re.DOTALL)

with open("core/standings.py", "w") as f:
    f.write(content)
