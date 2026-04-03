import random
from .models import Gameweek, Match, PlayerStat, Player, FantasyTeam, FantasyPick, Notification, LeagueMember

def simulate_match(match):
    # Realistic Poisson-style distribution for Premier League goals
    goal_weights = [0.26, 0.34, 0.22, 0.11, 0.05, 0.015, 0.005] 
    
    home_goals = random.choices(range(7), weights=goal_weights)[0]
    away_goals = random.choices(range(7), weights=goal_weights)[0]
    
    match.home_score = home_goals
    match.away_score = away_goals
    match.is_played = True
    match.save()
    
    home_players = list(Player.objects.filter(team=match.home_team, is_active=True))
    away_players = list(Player.objects.filter(team=match.away_team, is_active=True))
    
    _distribute_stats(home_players, match, home_goals, away_goals == 0)
    _distribute_stats(away_players, match, away_goals, home_goals == 0)

def _distribute_stats(players, match, goals_scored, clean_sheet):
    if not players: return
        
    active_players = []
    
    for p in players:
        # Handle existing injuries
        if p.is_injured:
            p.injury_weeks -= 1
            if p.injury_weeks <= 0:
                p.is_injured = False
                p.injury_weeks = 0
            p.save()
            continue

        # New Injury Roll (3% chance per game)
        if random.random() < 0.03:
            p.is_injured = True
            p.injury_weeks = random.randint(1, 3)
            p.save()
            
            impacted_picks = FantasyPick.objects.filter(player=p, fantasy_team__gameweek=match.gameweek)
            for pick in impacted_picks:
                Notification.objects.get_or_create(
                    user=pick.fantasy_team.user, 
                    message=f"🚨 INJURY ALERT: {p.display_name} has been injured for {p.injury_weeks} week(s)! Transfer them out before the next deadline."
                )
            continue

        # Playing Time Distribution (Heavily weighted by Price/Quality)
        start_prob = 0.10
        if p.price >= 9.0: start_prob = 0.95
        elif p.price >= 7.0: start_prob = 0.85
        elif p.price >= 5.5: start_prob = 0.70
        elif p.price >= 4.5: start_prob = 0.40
        
        minutes = 0
        if random.random() < start_prob:
            minutes = random.randint(60, 90)
        elif random.random() < 0.30: # Chance to come on as sub
            minutes = random.randint(1, 30)
            
        if minutes == 0: continue

        stat, _ = PlayerStat.objects.get_or_create(player=p, match=match)
        stat.minutes_played = minutes
        stat.clean_sheet = clean_sheet and minutes >= 60
        
        if random.random() < 0.10: stat.yellow_cards = 1
        if random.random() < 0.01: stat.red_cards = 1
        stat.save()
        
        active_players.append(p)

    if not active_players: return

    # Goal and Assist Weights (Exponentially favor expensive premium players)
    goal_weights = []
    assist_weights = []
    for p in active_players:
        # Base weight heavily scaling with price (e.g., 15m player weight is vastly larger than 4m)
        base_w = max(0.1, (p.price - 3.5)) ** 2.5 
        
        g_w = base_w
        if p.position == 'FWD': g_w *= 4.0
        elif p.position == 'MID': g_w *= 1.5
        elif p.position == 'DEF': g_w *= 0.2
        elif p.position == 'GK': g_w *= 0.01
        
        a_w = base_w
        if p.position == 'MID': a_w *= 2.5
        elif p.position == 'FWD': a_w *= 1.5
        elif p.position == 'DEF': a_w *= 0.8
        elif p.position == 'GK': a_w *= 0.02
        
        goal_weights.append(g_w)
        assist_weights.append(a_w)

    # Distribute actual goals
    for _ in range(goals_scored):
        scorer = random.choices(active_players, weights=goal_weights, k=1)[0]
        stat, _ = PlayerStat.objects.get_or_create(player=scorer, match=match)
        stat.goals += 1
        stat.save()
        
        # 75% chance a goal has an assist
        if random.random() < 0.75:
            assisters = [p for p in active_players if p != scorer]
            if assisters:
                a_weights = [assist_weights[active_players.index(p)] for p in assisters]
                assister = random.choices(assisters, weights=a_weights, k=1)[0]
                a_stat, _ = PlayerStat.objects.get_or_create(player=assister, match=match)
                a_stat.assists += 1
                a_stat.save()

def simulate_gameweek():
    active_gw = Gameweek.objects.filter(is_active=True).first()
    if not active_gw:
        return False
        
    matches = Match.objects.filter(gameweek=active_gw, is_played=False)
    for match in matches:
        simulate_match(match)
        
    fantasy_teams = FantasyTeam.objects.filter(gameweek=active_gw)
    for fteam in fantasy_teams:
        
        # Determine if the user is participating in any leagues
        in_league = LeagueMember.objects.filter(user=fteam.user).exists()
        
        raw_total_points = 0
        for pick in fteam.picks.all():
            if pick.is_sub:
                continue 
                
            stats = PlayerStat.objects.filter(player=pick.player, match__gameweek=active_gw)
            pts = sum(s.fantasy_points for s in stats)
            
            if pick.is_captain:
                pts *= 2
                
            # Keep natural points on the pick so the user sees how their players did
            pick.points_scored = pts
            pick.save()
            raw_total_points += pts
            
        # If not in a league, zero out their total gathered points for the week
        if not in_league:
            fteam.total_points = 0
            Notification.objects.get_or_create(
                user=fteam.user,
                message=f"GW{active_gw.number} Over: Your squad gathered 0 total points because you are not participating in any leagues! Join one to compete."
            )
        else:
            fteam.total_points = raw_total_points
            
        fteam.save()

    # Move timeline forward
    active_gw.is_active = False
    active_gw.save()
    
    next_gw = Gameweek.objects.filter(number=active_gw.number + 1).first()
    if next_gw:
        next_gw.is_active = True
        next_gw.save()
        
    return True
