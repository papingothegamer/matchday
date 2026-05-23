"""
seed_tournament — Demo Data Seeder
====================================
Creates demo users, fictional teams (with real EPL players mixed in),
a sample tournament, generated fixtures, and pre-played matches.

Usage: python manage.py seed_tournament
"""
import random
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import (
    Team, Player, Tournament, TournamentTeam, Match, PlayerStat, Standing,
)
from core.standings import recompute_standings, generate_league_fixtures


# ── Fictional team configs ──
FICTIONAL_TEAMS = [
    {'name': 'Phoenix United',     'short': 'PHX', 'color1': '#E63946', 'color2': '#FFFFFF'},
    {'name': 'Thunder FC',         'short': 'THU', 'color1': '#1D3557', 'color2': '#F1FAEE'},
    {'name': 'Emerald City',       'short': 'EMR', 'color1': '#2D6A4F', 'color2': '#FFFFFF'},
    {'name': 'Golden Eagles',      'short': 'GLE', 'color1': '#F4A261', 'color2': '#264653'},
    {'name': 'Iron Wolves',        'short': 'IWF', 'color1': '#343A40', 'color2': '#FFD166'},
    {'name': 'Royal Strikers',     'short': 'RYS', 'color1': '#6A0572', 'color2': '#FFFFFF'},
]

# ── Real EPL players pool (sourced from existing DB or hardcoded) ──
# Format: (first_name, last_name, position, jersey)
PLAYER_POOL = [
    # Goalkeepers
    ('Aaron', 'Ramsdale', 'GK', 1), ('David', 'Raya', 'GK', 1),
    ('Ederson', 'Moraes', 'GK', 31), ('Alisson', 'Becker', 'GK', 1),
    ('Jordan', 'Pickford', 'GK', 1), ('Robert', 'Sanchez', 'GK', 1),
    ('Andre', 'Onana', 'GK', 24), ('Bernd', 'Leno', 'GK', 1),
    ('Nick', 'Pope', 'GK', 22), ('Emiliano', 'Martinez', 'GK', 23),
    ('Alphonse', 'Areola', 'GK', 13), ('Sam', 'Johnstone', 'GK', 1),
    # Defenders
    ('William', 'Saliba', 'DEF', 2), ('Virgil', 'van Dijk', 'DEF', 4),
    ('Ruben', 'Dias', 'DEF', 3), ('Lisandro', 'Martinez', 'DEF', 6),
    ('Ben', 'White', 'DEF', 4), ('Trent', 'Alexander-Arnold', 'DEF', 66),
    ('Josko', 'Gvardiol', 'DEF', 24), ('Luke', 'Shaw', 'DEF', 23),
    ('Gabriel', 'Magalhaes', 'DEF', 6), ('Andrew', 'Robertson', 'DEF', 26),
    ('Kyle', 'Walker', 'DEF', 2), ('Diogo', 'Dalot', 'DEF', 20),
    ('Oleksandr', 'Zinchenko', 'DEF', 35), ('Tyrone', 'Mings', 'DEF', 40),
    ('Kieran', 'Trippier', 'DEF', 2), ('Ben', 'Chilwell', 'DEF', 21),
    ('Reece', 'James', 'DEF', 24), ('Marc', 'Cucurella', 'DEF', 3),
    ('Ezri', 'Konsa', 'DEF', 4), ('Jarrad', 'Branthwaite', 'DEF', 32),
    ('Lewis', 'Dunk', 'DEF', 5), ('Pervis', 'Estupinan', 'DEF', 30),
    ('Nathan', 'Ake', 'DEF', 6), ('Sven', 'Botman', 'DEF', 4),
    # Midfielders
    ('Martin', 'Odegaard', 'MID', 8), ('Kevin', 'De Bruyne', 'MID', 17),
    ('Bruno', 'Fernandes', 'MID', 8), ('Dominik', 'Szoboszlai', 'MID', 8),
    ('Declan', 'Rice', 'MID', 41), ('Rodri', 'Hernandez', 'MID', 16),
    ('Bukayo', 'Saka', 'MID', 7), ('Phil', 'Foden', 'MID', 47),
    ('Marcus', 'Rashford', 'MID', 10), ('Luis', 'Diaz', 'MID', 7),
    ('Leandro', 'Trossard', 'MID', 19), ('Bernardo', 'Silva', 'MID', 20),
    ('Casemiro', 'Casemiro', 'MID', 18), ('Alexis', 'Mac Allister', 'MID', 10),
    ('James', 'Maddison', 'MID', 10), ('Eberechi', 'Eze', 'MID', 10),
    ('Jorginho', 'Frello', 'MID', 20), ('Conor', 'Gallagher', 'MID', 23),
    ('Harvey', 'Elliott', 'MID', 19), ('Enzo', 'Fernandez', 'MID', 8),
    ('Moises', 'Caicedo', 'MID', 25), ('Youri', 'Tielemans', 'MID', 8),
    ('Douglas', 'Luiz', 'MID', 6), ('Bruno', 'Guimaraes', 'MID', 39),
    # Forwards
    ('Erling', 'Haaland', 'FWD', 9), ('Mohamed', 'Salah', 'FWD', 11),
    ('Alexander', 'Isak', 'FWD', 14), ('Ollie', 'Watkins', 'FWD', 11),
    ('Darwin', 'Nunez', 'FWD', 9), ('Julian', 'Alvarez', 'FWD', 19),
    ('Ivan', 'Toney', 'FWD', 17), ('Callum', 'Wilson', 'FWD', 9),
    ('Eddie', 'Nketiah', 'FWD', 14), ('Dominic', 'Calvert-Lewin', 'FWD', 9),
    ('Nicolas', 'Jackson', 'FWD', 15), ('Rodrigo', 'Muniz', 'FWD', 9),
    ('Gabriel', 'Jesus', 'FWD', 9), ('Jean-Philippe', 'Mateta', 'FWD', 14),
    ('Evan', 'Ferguson', 'FWD', 29), ('Jarrod', 'Bowen', 'FWD', 20),
]


class Command(BaseCommand):
    help = 'Seeds demo data: users, fictional teams with real EPL players, tournament, fixtures, and pre-played matches.'

    def handle(self, *args, **options):
        self.stdout.write('🧹 Clearing old data...')
        PlayerStat.objects.all().delete()
        Match.objects.all().delete()
        Standing.objects.all().delete()
        TournamentTeam.objects.all().delete()
        Player.objects.all().delete()
        Team.objects.all().delete()
        Tournament.objects.all().delete()

        # ── 1. Create Users ──
        self.stdout.write('👤 Creating users...')
        superadmin, _ = User.objects.get_or_create(username='superadmin', defaults={'is_staff': True, 'is_superuser': True})
        superadmin.set_password('admin123'); superadmin.save()

        league_admin, _ = User.objects.get_or_create(username='league_admin', defaults={'is_staff': True, 'is_superuser': False})
        league_admin.set_password('admin123'); league_admin.save()

        coaches = []
        for i in range(1, 7):
            coach, _ = User.objects.get_or_create(username=f'coach{i}', defaults={'is_staff': False})
            coach.set_password('admin123'); coach.save()
            coaches.append(coach)

        # ── 2. Create Fictional Teams & Distribute Players ──
        self.stdout.write('⚽ Creating fictional teams with real EPL players...')

        # Shuffle the player pool to get random distribution
        pool = list(PLAYER_POOL)
        random.shuffle(pool)

        # Ensure each team gets a balanced squad: 2 GK, 4 DEF, 4 MID, 3 FWD = 13 per team
        teams_created = []
        for idx, config in enumerate(FICTIONAL_TEAMS):
            coach = coaches[idx]
            team = Team.objects.create(
                name=config['name'],
                short_name=config['short'],
                primary_color=config['color1'],
                secondary_color=config['color2'],
                coach=coach,
            )
            teams_created.append(team)

        # Distribute by position
        gks = [p for p in pool if p[2] == 'GK']
        defs = [p for p in pool if p[2] == 'DEF']
        mids = [p for p in pool if p[2] == 'MID']
        fwds = [p for p in pool if p[2] == 'FWD']

        for idx, team in enumerate(teams_created):
            # Assign players: 2 GK, 4 DEF, 4 MID, 3 FWD
            team_gks = gks[idx*2:(idx+1)*2]
            team_defs = defs[idx*4:(idx+1)*4]
            team_mids = mids[idx*4:(idx+1)*4]
            team_fwds = fwds[idx*3:(idx+1)*3]

            jersey = 1
            for fname, lname, pos, _ in team_gks + team_defs + team_mids + team_fwds:
                Player.objects.create(
                    team=team, first_name=fname, last_name=lname,
                    position=pos, jersey_number=jersey,
                )
                jersey += 1

            self.stdout.write(f'  ✅ {team.name}: {team.players.count()} players')

        # ── 3. Create Tournament ──
        self.stdout.write('🏆 Creating tournament...')
        tournament = Tournament.objects.create(
            name='MatchDay Cup 2025',
            format='LEAGUE',
            status='ACTIVE',
            created_by=league_admin,
            description='A round-robin league tournament featuring 6 fictional teams with real EPL talent.',
        )

        for team in teams_created:
            TournamentTeam.objects.create(tournament=tournament, team=team)
            Standing.objects.get_or_create(tournament=tournament, team=team)

        # ── 4. Generate Fixtures ──
        self.stdout.write('📅 Generating fixtures...')
        matches = generate_league_fixtures(tournament)
        self.stdout.write(f'  Generated {len(matches)} matches.')

        # ── 5. Pre-play first 2 matchdays ──
        self.stdout.write('🎮 Simulating first 2 matchdays...')
        matchdays_to_play = ['Matchday 1', 'Matchday 2']

        for md in matchdays_to_play:
            md_matches = Match.objects.filter(tournament=tournament, round_label=md)
            for match in md_matches:
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
                    # Distribute goals among attackers/midfielders
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

                self.stdout.write(f'  ✅ {match}  →  {match.home_score}-{match.away_score}')

        # ── 6. Compute standings ──
        self.stdout.write('📊 Computing standings...')
        recompute_standings(tournament)

        self.stdout.write(self.style.SUCCESS('\n✅ Seeding complete! Here are your login credentials:'))
        self.stdout.write('  Super Admin:    superadmin / admin123')
        self.stdout.write('  League Admin:   league_admin / admin123')
        for i in range(1, 7):
            self.stdout.write(f'  Coach {i}:        coach{i} / admin123')
        self.stdout.write(f'\n  Tournament: "{tournament.name}" with {len(teams_created)} teams and {len(matches)} fixtures.')
        self.stdout.write(f'  Pre-played: Matchday 1 and Matchday 2.')
