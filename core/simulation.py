import random
from datetime import timedelta
from django.utils import timezone


def get_price_tier(price):
    if price >= 9.0:
        return 'elite'
    elif price >= 7.0:
        return 'premium'
    elif price >= 5.0:
        return 'mid'
    else:
        return 'budget'


TIER_PROBS = {
    'elite':   {'goal': 0.35, 'assist': 0.40, 'clean': 0.45, 'bonus': 0.50},
    'premium': {'goal': 0.22, 'assist': 0.30, 'clean': 0.35, 'bonus': 0.35},
    'mid':     {'goal': 0.12, 'assist': 0.20, 'clean': 0.28, 'bonus': 0.20},
    'budget':  {'goal': 0.05, 'assist': 0.10, 'clean': 0.20, 'bonus': 0.10},
}


def simulate_minutes():
    roll = random.random()
    if roll < 0.05:
        return 0
    elif roll < 0.15:
        return random.randint(45, 60)
    else:
        return random.randint(80, 90)


def simulate_player_stat(player, match):
    from core.models import PlayerStat
    tier = get_price_tier(player.price)
    probs = TIER_PROBS[tier]
    minutes = simulate_minutes()

    goals = 0
    assists = 0
    clean_sheet = False
    yellow = 0
    red = 0

    if minutes > 0:
        if player.position == 'GK':
            clean_sheet = random.random() < probs['clean']
            yellow = 1 if random.random() < 0.05 else 0

        elif player.position == 'DEF':
            clean_sheet = random.random() < probs['clean']
            goals = 1 if random.random() < probs['goal'] * 0.4 else 0
            assists = 1 if random.random() < probs['assist'] * 0.5 else 0
            yellow = 1 if random.random() < 0.08 else 0
            red = 1 if random.random() < 0.02 else 0

        elif player.position == 'MID':
            goals = 1 if random.random() < probs['goal'] else 0
            if goals == 0:
                goals = 2 if random.random() < probs['goal'] * 0.15 else 0
            assists = 1 if random.random() < probs['assist'] else 0
            if assists == 0:
                assists = 2 if random.random() < probs['assist'] * 0.1 else 0
            clean_sheet = random.random() < probs['clean'] * 0.3
            yellow = 1 if random.random() < 0.10 else 0
            red = 1 if random.random() < 0.02 else 0

        elif player.position == 'FWD':
            goals = 1 if random.random() < probs['goal'] else 0
            if goals == 0:
                goals = 2 if random.random() < probs['goal'] * 0.25 else 0
            if goals == 0:
                goals = 3 if random.random() < probs['goal'] * 0.05 else 0
            assists = 1 if random.random() < probs['assist'] * 0.7 else 0
            yellow = 1 if random.random() < 0.08 else 0
            red = 1 if random.random() < 0.02 else 0

    stat, _ = PlayerStat.objects.update_or_create(
        player=player, match=match,
        defaults={
            'goals': goals,
            'assists': assists,
            'minutes_played': minutes,
            'clean_sheet': clean_sheet,
            'yellow_cards': yellow,
            'red_cards': red,
        }
    )
    return stat


def simulate_gameweek(gameweek_number):
    from core.models import Gameweek, Match, Team, Player, FantasyTeam, FantasyPick

    try:
        gw = Gameweek.objects.get(number=gameweek_number)
    except Gameweek.DoesNotExist:
        print(f'Gameweek {gameweek_number} not found.')
        return

    teams = list(Team.objects.all())
    random.shuffle(teams)

    # Pair teams into fixtures if none exist
    existing_matches = Match.objects.filter(gameweek=gw)
    if not existing_matches.exists():
        kick_off_times = _get_kickoff_times(gw.deadline)
        fixtures = []
        paired = []
        for i in range(0, min(len(teams), 20), 2):
            if i + 1 < len(teams):
                paired.append((teams[i], teams[i+1]))
        for idx, (home, away) in enumerate(paired):
            ko = kick_off_times[idx % len(kick_off_times)]
            match = Match.objects.create(
                home_team=home, away_team=away,
                gameweek=gw, match_date=ko,
                is_played=False,
            )
            fixtures.append(match)
    else:
        fixtures = list(existing_matches)

    print(f'Simulating {len(fixtures)} matches for GW{gameweek_number}...')

    total_goals_home = 0
    total_goals_away = 0

    for match in fixtures:
        home_players = Player.objects.filter(team=match.home_team, is_active=True)
        away_players = Player.objects.filter(team=match.away_team, is_active=True)

        home_goals = 0
        away_goals = 0

        for player in home_players:
            stat = simulate_player_stat(player, match)
            home_goals += stat.goals

        for player in away_players:
            stat = simulate_player_stat(player, match)
            away_goals += stat.goals

        match.home_score = home_goals
        match.away_score = away_goals
        match.is_played = True
        match.save()

        total_goals_home += home_goals
        total_goals_away += away_goals
        print(f'  {match.home_team.short_name} {home_goals} - {away_goals} {match.away_team.short_name}')

    # Update fantasy team points
    fantasy_teams = FantasyTeam.objects.filter(gameweek=gw)
    for ft in fantasy_teams:
        gw_points = 0
        for pick in ft.picks.select_related('player'):
            player_stats = pick.player.stats.filter(match__gameweek=gw)
            pts = sum(s.fantasy_points for s in player_stats)
            if pick.is_captain:
                pts *= 2
            pick.points_scored = pts
            pick.save()
            gw_points += pts
        ft.total_points = gw_points
        ft.save()
        print(f'  {ft.user.username}: {gw_points} pts')

    gw.is_active = False
    gw.save()

    # Activate next gameweek
    next_gw = Gameweek.objects.filter(number=gameweek_number + 1).first()
    if next_gw:
        next_gw.is_active = True
        next_gw.save()
        print(f'GW{next_gw.number} is now active.')

    print(f'GW{gameweek_number} simulation complete.')


def _get_kickoff_times(deadline):
    base = deadline - timedelta(days=7)
    times = [
        base + timedelta(days=0, hours=15),
        base + timedelta(days=0, hours=17, minutes=30),
        base + timedelta(days=1, hours=14),
        base + timedelta(days=1, hours=16, minutes=30),
        base + timedelta(days=3, hours=19, minutes=45),
        base + timedelta(days=3, hours=19, minutes=45),
        base + timedelta(days=4, hours=19, minutes=45),
        base + timedelta(days=4, hours=19, minutes=45),
        base + timedelta(days=5, hours=19, minutes=45),
        base + timedelta(days=6, hours=12, minutes=30),
    ]
    return times
