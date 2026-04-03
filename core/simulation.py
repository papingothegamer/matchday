import random
from .models import Gameweek, Match, PlayerStat, Player, FantasyTeam, FantasyPick, Notification, LeagueMember

def get_goal_weights(strength_ratio):
    # Default distribution: ~1.4 goals per team
    base = [0.26, 0.34, 0.22, 0.11, 0.05, 0.015, 0.005]
    if strength_ratio > 1.3: # Strong favorite (e.g. Man City vs Burnley)
        return [0.10, 0.20, 0.30, 0.25, 0.10, 0.04, 0.01] # Average ~2.2 goals
    elif strength_ratio < 0.77: # Heavy underdog
        return [0.45, 0.35, 0.15, 0.04, 0.01, 0.00, 0.00] # Average ~0.8 goals
    return base

def simulate_match(match):
    home_players = list(Player.objects.filter(team=match.home_team, is_active=True))
    away_players = list(Player.objects.filter(team=match.away_team, is_active=True))
    
    # Calculate Dynamic Team Strength (Top 6 teams naturally have higher total values)
    home_strength = sum(p.price for p in home_players)
    away_strength = sum(p.price for p in away_players)
    
    # Add a 10% intrinsic home-field advantage
    home_ratio = (home_strength * 1.1) / (away_strength if away_strength > 0 else 1)
    away_ratio = away_strength / (home_strength * 1.1 if home_strength > 0 else 1)

    home_goals = random.choices(range(7), weights=get_goal_weights(home_ratio))[0]
    away_goals = random.choices(range(7), weights=get_goal_weights(away_ratio))[0]
    
    match.home_score = home_goals
    match.away_score = away_goals
    match.is_played = True
    match.save()
    
    _distribute_stats(home_players, match, home_goals, away_goals == 0)
    _distribute_stats(away_players, match, away_goals, home_goals == 0)

def _distribute_stats(players, match, goals_scored, clean_sheet):
    if not players: return
        
    active_players = []
    
    for p in players:
        if p.is_injured:
            p.injury_weeks -= 1
            if p.injury_weeks <= 0:
                p.is_injured = False
                p.injury_weeks = 0
            p.save()
            continue

        if random.random() < 0.03:
            p.is_injured = True
            p.injury_weeks = random.randint(1, 3)
            p.save()
            impacted_picks = FantasyPick.objects.filter(player=p, fantasy_team__gameweek=match.gameweek)
            for pick in impacted_picks:
                Notification.objects.get_or_create(
                    user=pick.fantasy_team.user, 
                    message=f"🚨 INJURY ALERT: {p.display_name} has been injured for {p.injury_weeks} week(s)!"
                )
            continue

        # Strict Academy Player Filter: Min price players rarely even start
        start_prob = min(0.98, max(0.02, (p.price - 4.0) / 4.0)) 
        
        minutes = 0
        if random.random() < start_prob:
            minutes = random.randint(60, 90)
        elif random.random() < 0.15: # Sub appearance
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

    # Goal and Assist Weights (Power of 3 exponentially favors premium players)
    goal_weights = []
    assist_weights = []
    for p in active_players:
        base_w = (max(0.1, p.price - 4.0)) ** 3.0 
        
        g_w = base_w
        if p.position == 'FWD': g_w *= 4.0
        elif p.position == 'MID': g_w *= 1.5
        elif p.position == 'DEF': g_w *= 0.1
        elif p.position == 'GK': g_w *= 0.001
        
        a_w = base_w
        if p.position == 'MID': a_w *= 2.5
        elif p.position == 'FWD': a_w *= 1.5
        elif p.position == 'DEF': a_w *= 0.8
        elif p.position == 'GK': a_w *= 0.01
        
        goal_weights.append(g_w)
        assist_weights.append(a_w)

    for _ in range(goals_scored):
        scorer = random.choices(active_players, weights=goal_weights, k=1)[0]
        stat, _ = PlayerStat.objects.get_or_create(player=scorer, match=match)
        stat.goals += 1
        stat.save()
        
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
    if not active_gw: return False
        
    matches = Match.objects.filter(gameweek=active_gw, is_played=False)
    for match in matches: simulate_match(match)
        
    fantasy_teams = FantasyTeam.objects.filter(gameweek=active_gw)
    for fteam in fantasy_teams:
        in_league = LeagueMember.objects.filter(user=fteam.user).exists()
        raw_total_points = 0
        
        for pick in fteam.picks.all():
            if pick.is_sub: continue 
            stats = PlayerStat.objects.filter(player=pick.player, match__gameweek=active_gw)
            pts = sum(s.fantasy_points for s in stats)
            if pick.is_captain: pts *= 2
            pick.points_scored = pts
            pick.save()
            raw_total_points += pts
            
        if not in_league:
            fteam.total_points = 0
            Notification.objects.get_or_create(
                user=fteam.user,
                message=f"GW{active_gw.number} Over: Your squad gathered 0 points because you are not in any leagues! Join one to compete."
            )
        else:
            fteam.total_points = raw_total_points
        fteam.save()

    active_gw.is_active = False
    active_gw.save()
    next_gw = Gameweek.objects.filter(number=active_gw.number + 1).first()
    if next_gw:
        next_gw.is_active = True
        next_gw.save()
    return True
