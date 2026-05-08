import os
import re
import random
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'matchday.settings')
django.setup()

from core.models import Team, Player, Gameweek
from datetime import datetime, timezone, timedelta
from core.models import Team, Player, Gameweek, Match
from core.simulation import simulate_match

print("Clearing existing data...")
Match.objects.all().delete()
Player.objects.all().delete()
Team.objects.all().delete()
Gameweek.objects.all().delete()

# Map of the 20 PL clubs with Logo Filenames
teams_data = {
    'Arsenal': ('ARS', 'Emirates Stadium', 1886, '#EF0107', '#FFFFFF', 'Arsenal_FC.png'),
    'Aston Villa': ('AVL', 'Villa Park', 1874, '#95BFE5', '#670E36', 'Aston_Villa_FC_new_crest.svg.png'),
    'Bournemouth': ('BOU', 'Vitality Stadium', 1899, '#DA291C', '#000000', 'AFC_Bournemouth_(2013).svg.png'),
    'Brentford': ('BRE', 'Gtech Community Stadium', 1889, '#E30613', '#FFFFFF', 'Brentford_FC_logo.png'),
    'Brighton & Hove Albion': ('BHA', 'Amex Stadium', 1901, '#0057B8', '#FFFFFF', 'Brighton_&_Hove_Albion_logo.svg.png'),
    'Burnley': ('BUR', 'Turf Moor', 1882, '#6C1D45', '#99D6EA', 'burnley.2c75b6ce.png'),
    'Chelsea': ('CHE', 'Stamford Bridge', 1905, '#034694', '#FFFFFF', 'chelsea.66e570b4.png'),
    'Crystal Palace': ('CRY', 'Selhurst Park', 1905, '#1B458F', '#C4122E', 'Crystal_Palace_FC_logo.png'),
    'Everton': ('EVE', 'Goodison Park', 1878, '#003399', '#FFFFFF', 'Everton_FC_logo.svg.png'),
    'Fulham': ('FUL', 'Craven Cottage', 1879, '#FFFFFF', '#000000', 'fulham.a93cda89.png'),
    'Leeds United': ('LEE', 'Elland Road', 1919, '#FFCD00', '#1D428A', 'leeds-united-afc-3-logo-png-transparent.png'),
    'Liverpool': ('LIV', 'Anfield', 1892, '#C8102E', '#FFFFFF', 'liverpool.abccda5c.png'),
    'Manchester City': ('MCI', 'Etihad Stadium', 1880, '#6CABDD', '#FFFFFF', 'Manchester_City_FC_badge.svg.png'),
    'Manchester United': ('MUN', 'Old Trafford', 1878, '#DA291C', '#FFE500', 'Manchester_United_FC_crest.png'),
    'Newcastle United': ('NEW', "St. James' Park", 1892, '#241F20', '#FFFFFF', 'Newcastle_United_Logo.svg.png'),
    'Nottingham Forest': ('NFO', 'City Ground', 1865, '#DD0000', '#FFFFFF', 'nottingham-forest.84fbc04b.png'),
    'Sunderland': ('SUN', 'Stadium of Light', 1879, '#FF0000', '#FFFFFF', 'Logo_Sunderland.png'),
    'Tottenham Hotspur': ('TOT', 'Tottenham Hotspur Stadium', 1882, '#132257', '#FFFFFF', 'Tottenham_Hotspur.png'),
    'West Ham United': ('WHU', 'London Stadium', 1895, '#7A263A', '#1BB1E7', 'West_Ham_United_FC_logo.svg.png'),
    'Wolverhampton Wanderers': ('WOL', 'Molineux Stadium', 1877, '#FDB913', '#231F20', 'Wolverhampton_Wanderers.svg.png'),
}

# Club Tiers for Baseline Pricing
tier_1 = ['MCI', 'ARS', 'LIV', 'CHE', 'TOT', 'MUN', 'NEW', 'AVL']
tier_2 = ['BHA', 'WHU', 'CRY', 'FUL', 'BOU', 'BRE']

# Hardcoded Overrides for Premium FPL Assets
premium_prices = {
    "Erling Håland": 15.0,
    "Mohamed Salah": 12.5,
    "Cole Palmer": 10.5,
    "Alexander Isak": 10.0,
    "Bukayo Saka": 10.0,
    "Son Heung-min": 10.0,
    "Phil Foden": 9.5,
    "Kevin De Bruyne": 9.5,
    "Ollie Watkins": 9.0,
    "Martin Ødegaard": 8.5,
    "Bruno Fernandes": 8.5,
    "Declan Rice": 8.5,
    "Rodri": 8.5,
    "Bernardo Silva": 8.0,
    "Anthony Gordon": 8.0,
    "Luis Díaz": 8.0,
    "Diogo Jota": 7.5,
    "Kai Havertz": 8.0,
    "Alexis Mac Allister": 7.5,
    "James Maddison": 7.5,
    "Marcus Rashford": 7.5,
    "Alejandro Garnacho": 7.0,
    "Trent Alexander-Arnold": 7.0,
    "Ben White": 6.5,
    "William Saliba": 6.0,
    "Joško Gvardiol": 6.0,
    "Gabriel": 6.0,
    "Virgil van Dijk": 6.0,
    "Cristian Romero": 6.0,
    "Ruben Dias": 6.0,
    "Kieran Trippier": 6.0,
    "Pedro Porro": 5.5,
    "David Raya": 5.5,
    "Alisson Becker": 5.5,
    "Ederson": 5.5,
    "Emiliano Martínez": 5.5,
}

def calculate_price(full_name, pos, team_short):
    if full_name in premium_prices:
        return premium_prices[full_name]
    
    if team_short in tier_1:
        if pos == 'FWD': return round(random.uniform(6.5, 8.0) * 2) / 2
        if pos == 'MID': return round(random.uniform(5.5, 7.5) * 2) / 2
        if pos == 'DEF': return round(random.uniform(4.5, 5.5) * 2) / 2
        if pos == 'GK': return round(random.uniform(4.5, 5.0) * 2) / 2
    elif team_short in tier_2:
        if pos == 'FWD': return round(random.uniform(5.5, 7.0) * 2) / 2
        if pos == 'MID': return round(random.uniform(5.0, 6.5) * 2) / 2
        if pos == 'DEF': return round(random.uniform(4.0, 5.0) * 2) / 2
        if pos == 'GK': return round(random.uniform(4.0, 4.5) * 2) / 2
    else: # Tier 3
        if pos == 'FWD': return round(random.uniform(4.5, 6.0) * 2) / 2
        if pos == 'MID': return round(random.uniform(4.5, 5.5) * 2) / 2
        if pos == 'DEF': return round(random.uniform(4.0, 4.5) * 2) / 2
        if pos == 'GK': return round(random.uniform(4.0, 4.5) * 2) / 2
    
    return 4.5

try:
    with open('PL.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()
except FileNotFoundError:
    print("Error: PL.txt not found.")
    exit()

print("Parsing PL.txt and assigning dynamic FPL pricing...")

pos_map = {'G': 'GK', 'D': 'DEF', 'M': 'MID', 'F': 'FWD'}

current_team = None
parsing_players = False
player_count = 0

for line in lines:
    line = line.strip()
    if not line: continue

    if line in teams_data:
        short, stadium, founded, primary, secondary, logo = teams_data[line]
        current_team, _ = Team.objects.get_or_create(
            name=line,
            defaults={'short_name': short, 'stadium': stadium, 'founded_year': founded, 'primary_color': primary, 'secondary_color': secondary, 'logo_filename': logo}
        )
        current_team.logo_filename = logo
        current_team.save()
        parsing_players = False
        continue

    if "Number\tName\tNat\tPos" in line:
        parsing_players = True
        continue

    if "Players no longer at this club" in line:
        parsing_players = False
        current_team = None
        continue

    if parsing_players and current_team:
        parts = line.split('\t')
        if len(parts) >= 4:
            num_str = parts[0].strip()
            if not num_str.isdigit(): continue
            full_name = parts[1].strip()
            if not full_name: continue
            name_parts = full_name.split(' ')
            first_name = name_parts[0] if len(name_parts) > 1 else ''
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else name_parts[0]
            pos_char = parts[3].strip()
            pos = pos_map.get(pos_char, 'MID')
            price = calculate_price(full_name, pos, current_team.short_name)
            Player.objects.create(team=current_team, first_name=first_name, last_name=last_name, position=pos, price=price, is_active=True)
            player_count += 1

print(f"Successfully imported {player_count} active players!")

print("Generating 38 Gameweeks and Fixtures...")

gws = []
# Fixed reference: GW36 deadline is Monday, May 11, 2026 (assuming a Monday deadline for this specific week)
gw36_deadline = datetime(2026, 5, 11, 11, 0, tzinfo=timezone.utc)

for i in range(1, 39):
    weeks_diff = i - 36
    deadline = gw36_deadline + timedelta(weeks=weeks_diff)
    gw = Gameweek.objects.create(number=i, deadline=deadline, is_active=(i == 36))
    gws.append(gw)

teams = list(Team.objects.all())
n = len(teams)

# Realistic Scheduling Pattern (relative to deadline)
# 0: Fri Eve, 1-5: Sat, 6-8: Sun, 9: Mon Eve
offsets = [
    timedelta(hours=8), # Fri 19:00
    timedelta(days=1, hours=4), # Sat 15:00
    timedelta(days=1, hours=4), # Sat 15:00
    timedelta(days=1, hours=4), # Sat 15:00
    timedelta(days=1, hours=6), # Sat 17:30
    timedelta(days=1, hours=9), # Sat 20:00
    timedelta(days=2, hours=3), # Sun 14:00
    timedelta(days=2, hours=5), # Sun 16:30
    timedelta(days=2, hours=8), # Sun 19:30
    timedelta(days=3, hours=9), # Mon 20:00
]

for i in range(38):
    gw = gws[i]
    # Shuffle teams for variety each week
    random.shuffle(teams)
    
    # Ensure every team plays exactly once (Round Robin)
    # Using a simple pairing for the import script
    for j in range(n // 2):
        home = teams[j]
        away = teams[n - 1 - j]
        
        # Apply the realistic offset
        match_date = gw.deadline + offsets[j % 10]
        match = Match.objects.create(gameweek=gw, home_team=home, away_team=away, match_date=match_date)
        
        if gw.number < 36:
            simulate_match(match)

print(f"Simulation of GW1-35 complete. GW36 is now Active.")
print("Fixtures spread realistically across Friday to Monday.")
print("Setup Complete!")
