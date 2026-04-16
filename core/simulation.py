import random
from .models import Gameweek, Match, Player, PlayerStat, FantasyTeam, LeagueMember, Notification

def update_player_prices(gw):
    pass

def simulate_match(match):
    if match.is_played: return
    
    match.home_score = random.choices([0, 1, 2, 3, 4], weights=[30, 35, 20, 10, 5])[0]
    match.away_score = random.choices([0, 1, 2, 3, 4], weights=[35, 30, 20, 10, 5])[0]
    match.is_played = True
    match.save()
    
    def gen_stats(team, goals_scored, goals_conceded):
        players = list(Player.objects.filter(team=team))
        if not players: return
        avail = [p for p in players if not p.is_injured]
        unavail = [p for p in players if p.is_injured]
        stats = []
        for p in unavail:
            stats.append(PlayerStat(match=match, player=p, minutes_played=0, goals=0, assists=0, fantasy_points=0))
        random.shuffle(avail)
        starters = avail[:11]
        bench = avail[11:]
        num_subs = min(random.randint(3, 5), len(bench))
        actual_subs = bench[:num_subs]
        for p in bench[num_subs:]:
            stats.append(PlayerStat(match=match, player=p, minutes_played=0, goals=0, assists=0, fantasy_points=0))
            
        gs = random.choices([p for p in starters + actual_subs if p.position in ['FWD', 'MID', 'DEF']], k=goals_scored) if goals_scored > 0 else []
        asts = random.choices([p for p in starters + actual_subs if p.position in ['MID', 'FWD', 'DEF']], k=goals_scored) if goals_scored > 0 else []
        
        for p in starters + actual_subs:
            if p in starters:
                mins = random.randint(45, 80) if (num_subs > 0 and random.random() < 0.25) else 90
                if mins < 90: num_subs -= 1
            else:
                mins = random.randint(1, 45)
                
            g = gs.count(p)
            a = asts.count(p)
            pts = 2 if mins >= 60 else (1 if mins > 0 else 0)
            if goals_conceded == 0 and mins >= 60:
                if p.position in ['GK', 'DEF']: pts += 4
                elif p.position == 'MID': pts += 1
            if p.position in ['GK', 'DEF']: pts += g * 6
            elif p.position == 'MID': pts += g * 5
            elif p.position == 'FWD': pts += g * 4
            pts += a * 3
            if mins > 0 and random.random() < 0.1: pts -= 1
            stats.append(PlayerStat(match=match, player=p, minutes_played=mins, goals=g, assists=a, fantasy_points=pts))
        PlayerStat.objects.bulk_create(stats)

    gen_stats(match.home_team, match.home_score, match.away_score)
    gen_stats(match.away_team, match.away_score, match.home_score)

def simulate_gameweek(gw=None):
    active_gw = gw or Gameweek.objects.filter(is_active=True).first()
    if not active_gw: return False
        
    matches = Match.objects.filter(gameweek=active_gw, is_played=False)
    for match in matches: simulate_match(match)
        
    fantasy_teams = FantasyTeam.objects.filter(gameweek=active_gw)
    for fteam in fantasy_teams:
        in_league = LeagueMember.objects.filter(user=fteam.user).exists()
        
        picks = list(fteam.picks.all())
        pick_stats = {}
        for pick in picks:
            stats = PlayerStat.objects.filter(player=pick.player, match__gameweek=active_gw)
            mins = sum(s.minutes_played for s in stats)
            pts = sum(s.fantasy_points for s in stats)
            pick_stats[pick.id] = {'mins': mins, 'pts': pts}

        c_pick = next((p for p in picks if p.is_captain), None)
        vc_pick = next((p for p in picks if getattr(p, 'is_vice_captain', False)), None)
        active_cap = c_pick
        if c_pick and pick_stats[c_pick.id]['mins'] == 0:
            if vc_pick and pick_stats[vc_pick.id]['mins'] > 0:
                active_cap = vc_pick
            else:
                active_cap = None

        active_starters = [p for p in picks if not p.is_sub]
        available_subs = [p for p in picks if p.is_sub]

        s_gk = next((p for p in active_starters if p.player.position == 'GK'), None)
        b_gk = next((p for p in available_subs if p.player.position == 'GK'), None)
        if s_gk and pick_stats[s_gk.id]['mins'] == 0 and b_gk and pick_stats[b_gk.id]['mins'] > 0:
            active_starters.remove(s_gk)
            active_starters.append(b_gk)
            available_subs.remove(b_gk)

        def get_counts(arr):
            c = {'DEF':0, 'MID':0, 'FWD':0}
            for p in arr:
                if p.player.position in c: c[p.player.position] += 1
            return c

        outfield_starters = [p for p in active_starters if p.player.position != 'GK']
        outfield_subs = [p for p in available_subs if p.player.position != 'GK']

        for s in list(outfield_starters):
            if pick_stats[s.id]['mins'] == 0:
                for b in list(outfield_subs):
                    if pick_stats[b.id]['mins'] > 0:
                        test_arr = list(active_starters)
                        test_arr.remove(s)
                        test_arr.append(b)
                        counts = get_counts(test_arr)
                        if counts['DEF'] >= 3 and counts['MID'] >= 2 and counts['FWD'] >= 1:
                            active_starters = test_arr
                            outfield_subs.remove(b)
                            break

        total = 0
        for p in picks:
            pts = pick_stats[p.id]['pts']
            if p in active_starters:
                if p == active_cap:
                    pts *= 2
                p.points_scored = pts
                total += pts
            else:
                p.points_scored = pts
            p.save()
            
        fteam.total_points = total
        if not in_league:
            Notification.objects.get_or_create(user=fteam.user, message=f"GW{active_gw.number} finished! You scored {total} pts.")
        fteam.save()

    active_gw.is_active = False
    active_gw.save()
    next_gw = Gameweek.objects.filter(number=active_gw.number + 1).first()
    if next_gw:
        next_gw.is_active = True
        next_gw.save()
    return True
