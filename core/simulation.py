import random
from .models import Gameweek, Match, PlayerStat, Player, FantasyTeam, FantasyPick, Notification

def simulate_match(match):
    # Realistic Poisson-style distribution for Premier League goals
    # Averages ~2.7 goals per match overall. Massive scores (>4) are incredibly rare.
    goal_weights = [0.26, 0.34, 0.22, 0.11, 0.05, 0.015, 0.005] # Probability of 0 to 6 goals
    
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
            # Send Notification to users who own this player
            impacted_picks = FantasyPick.objects.filter(player=p, fantasy_team__gameweek=match.gameweek)
            for pick in impacted_picks:
                Notification.objects.get_or_create(
                    user=pick.fantasy_team.user, 
                    message=f"🚨 INJURY ALERT: {p.display_name} has been injured for {p.injury_weeks} week(s)! Transfer them out before the next deadline."
                )
            continue

        # Playing Time Distribution
        minutes = 0
        if random.random() < 0.85: minutes = random.randint(60, 90)
        elif random.random() < 0.40: minutes = random.randint(1, 59)
            
        if minutes == 0: continue

        stat, _ = PlayerStat.objects.get_or_create(player=p, match=match)
        stat.minutes_played = minutes
        stat.clean_sheet = clean_sheet and minutes >= 60
        
        if random.random() < 0.15: stat.yellow_cards = 1
        if random.random() < 0.02: stat.red_cards = 1
        stat.save()

    active_players = [p for p in players if not p.is_injured]
    if not active_players: return

    # Distribute actual goals to random active players
    for _ in range(goals_scored):
        scorer = random.choice(active_players)
        stat, _ = PlayerStat.objects.get_or_create(player=scorer, match=match)
        stat.goals += 1
        stat.save()
        
        # 70% chance a goal has an assist
        if random.random() < 0.70:
            assisters = [p for p in active_players if p != scorer]
            if assisters:
                assister = random.choice(assisters)
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
        total_points = 0
        for pick in fteam.picks.all():
            if pick.is_sub:
                continue 
                
            stats = PlayerStat.objects.filter(player=pick.player, match__gameweek=active_gw)
            pts = sum(s.fantasy_points for s in stats)
            if pick.is_captain:
                pts *= 2
            pick.points_scored = pts
            pick.save()
            total_points += pts
            
        fteam.total_points = total_points
        fteam.save()

    # Move timeline forward
    active_gw.is_active = False
    active_gw.save()
    
    next_gw = Gameweek.objects.filter(number=active_gw.number + 1).first()
    if next_gw:
        next_gw.is_active = True
        next_gw.save()
        
    return True
