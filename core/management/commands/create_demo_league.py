import random
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Team, Player, Gameweek, FantasyTeam, FantasyPick, PlayerStat, League, LeagueMember
from django.db.models import Sum

class Command(BaseCommand):
    help = 'Creates a demo league with 15 bots, realistic squads, and historical points up to GW35.'

    def handle(self, *args, **kwargs):
        self.stdout.write('Initializing Demo League...')
        
        # 1. Create the League
        admin_user = User.objects.filter(is_superuser=True).first()
        league, created = League.objects.get_or_create(
            name="Global Elite Showcase",
            defaults={'code': 'DEMO2026', 'created_by': admin_user}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created League: {league.name} (Code: {league.code})'))

        # 2. Identify Human Users
        humans = list(User.objects.filter(is_superuser=False).exclude(username__startswith='bot_'))
        for h in humans:
            LeagueMember.objects.get_or_create(user=h, league=league)
            self.stdout.write(f'Added human user {h.username} to the league.')

        # 3. Create 15 Bots
        bots = []
        for i in range(1, 16):
            username = f'bot_{i}'
            email = f'{username}@matchday.demo'
            bot, b_created = User.objects.get_or_create(username=username, defaults={'email': email})
            if b_created:
                bot.set_password('demo_pass_123')
                bot.save()
            bots.append(bot)
            LeagueMember.objects.get_or_create(user=bot, league=league)

        self.stdout.write(f'Synced 15 bots to the league.')

        # 4. Include Human Users in squad generation
        all_participants = bots + humans

        # 5. Generate Teams and Picks
        all_gws = Gameweek.objects.filter(number__lte=36).order_by('number')
        players_by_pos = {
            'GK': list(Player.objects.filter(position='GK')),
            'DEF': list(Player.objects.filter(position='DEF')),
            'MID': list(Player.objects.filter(position='MID')),
            'FWD': list(Player.objects.filter(position='FWD')),
        }

        for user in all_participants:
            is_bot = user.username.startswith('bot_')
            
            # If it's a human user, we ONLY create the team container if it doesn't exist
            # We NEVER touch their picks or bank.
            if not is_bot:
                self.stdout.write(f'Checking human user {user.username}...')
                for gw in all_gws:
                    FantasyTeam.objects.get_or_create(
                        user=user,
                        gameweek=gw,
                        defaults={'name': f"{user.username.capitalize()}'s XI"}
                    )
                continue # Skip the rest of the generation for humans

            self.stdout.write(f'Generating squad for {user.username}...')
            
            # Elite Selection for Bots (top 40 players)
            squad = []
            for pos, count in [('GK', 2), ('DEF', 5), ('MID', 5), ('FWD', 3)]:
                available = sorted(players_by_pos[pos], key=lambda x: x.price, reverse=True)
                squad.extend(random.sample(available[:40], count))
            
            for gw in all_gws:
                fteam, ft_created = FantasyTeam.objects.get_or_create(
                    user=user,
                    gameweek=gw,
                    defaults={'name': f"{user.username.capitalize()}'s XI"}
                )
                
                if fteam.picks.count() == 0:
                    pos_counts = {'GK': 0, 'DEF': 0, 'MID': 0, 'FWD': 0}
                    starters_count = {'GK': 1, 'DEF': 4, 'MID': 4, 'FWD': 2}
                    has_cap = False
                    has_vc = False
                    
                    for player in squad:
                        is_sub = False
                        if pos_counts[player.position] >= starters_count[player.position]:
                            is_sub = True
                        pos_counts[player.position] += 1
                        
                        is_cap = False
                        is_vc = False
                        if not is_sub and not has_cap:
                            is_cap = True
                            has_cap = True
                        elif not is_sub and not has_vc:
                            is_vc = True
                            has_vc = True
                            
                        FantasyPick.objects.create(
                            fantasy_team=fteam,
                            player=player,
                            is_captain=is_cap,
                            is_vice_captain=is_vc,
                            is_sub=is_sub,
                            purchase_price=player.price
                        )
                    
                    # Calculate Points for this GW (if it's in the past)
                    if gw.number < 36:
                        # Fetch stats for these players in this GW
                        total_gw_pts = 0
                        for p in FantasyPick.objects.filter(fantasy_team=fteam):
                            stats = PlayerStat.objects.filter(player=p.player, match__gameweek=gw)
                            pts = sum(s.fantasy_points for s in stats)
                            if not p.is_sub:
                                if p.is_captain: pts *= 2
                                total_gw_pts += pts
                            p.points_scored = pts
                            p.save()
                        
                        fteam.total_points = total_gw_pts
                        fteam.save()

        self.stdout.write(self.style.SUCCESS('Demo League successfully populated with historical data!'))
