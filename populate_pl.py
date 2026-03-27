import os
import re
import random
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'matchday.settings')
django.setup()

from core.models import Team, Player, Gameweek
from datetime import datetime, timezone

print("Clearing existing data...")
Player.objects.all().delete()
Team.objects.all().delete()
Gameweek.objects.all().delete()

# Map of the 20 PL clubs
teams_data = {
    'Arsenal': ('ARS', 'Emirates Stadium', 1886, '#EF0107', '#FFFFFF'),
    'Aston Villa': ('AVL', 'Villa Park', 1874, '#95BFE5', '#670E36'),
    'Bournemouth': ('BOU', 'Vitality Stadium', 1899, '#DA291C', '#000000'),
    'Brentford': ('BRE', 'Gtech Community Stadium', 1889, '#E30613', '#FFFFFF'),
    'Brighton & Hove Albion': ('BHA', 'Amex Stadium', 1901, '#0057B8', '#FFFFFF'),
    'Burnley': ('BUR', 'Turf Moor', 1882, '#6C1D45', '#99D6EA'),
    'Chelsea': ('CHE', 'Stamford Bridge', 1905, '#034694', '#FFFFFF'),
    'Crystal Palace': ('CRY', 'Selhurst Park', 1905, '#1B458F', '#C4122E'),
    'Everton': ('EVE', 'Goodison Park', 1878, '#003399', '#FFFFFF'),
    'Fulham': ('FUL', 'Craven Cottage', 1879, '#FFFFFF', '#000000'),
    'Leeds United': ('LEE', 'Elland Road', 1919, '#FFCD00', '#1D428A'),
    'Liverpool': ('LIV', 'Anfield', 1892, '#C8102E', '#FFFFFF'),
    'Manchester City': ('MCI', 'Etihad Stadium', 1880, '#6CABDD', '#FFFFFF'),
    'Manchester United': ('MUN', 'Old Trafford', 1878, '#DA291C', '#FFE500'),
    'Newcastle United': ('NEW', "St. James' Park", 1892, '#241F20', '#FFFFFF'),
    'Nottingham Forest': ('NFO', 'City Ground', 1865, '#DD0000', '#FFFFFF'),
    'Sunderland': ('SUN', 'Stadium of Light', 1879, '#FF0000', '#FFFFFF'),
    'Tottenham Hotspur': ('TOT', 'Tottenham Hotspur Stadium', 1882, '#132257', '#FFFFFF'),
    'West Ham United': ('WHU', 'London Stadium', 1895, '#7A263A', '#1BB1E7'),
    'Wolverhampton Wanderers': ('WOL', 'Molineux Stadium', 1877, '#FDB913', '#231F20'),
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
    "Son Heung-min": 9.0,
    "Phil Foden": 9.5,
    "Kevin De Bruyne": 9.5,
    "Ollie Watkins": 9.0,
    "Martin Ødegaard": 8.5,
    "Bruno Fernandes": 8.5,
    "Florian Wirtz": 8.5,
    "Eberechi Eze": 8.5,
    "Viktor Gyökeres": 8.5,
    "Anthony Gordon": 8.0,
    "Luis Díaz": 7.5,
    "Diogo Jota": 7.5,
    "Trent Alexander-Arnold": 7.0,
    "Ben White": 6.5,
    "William Saliba": 6.0,
    "Joško Gvardiol": 6.0,
    "Gabriel": 6.0,
    "Virgil van Dijk": 6.0,
    "Kieran Trippier": 6.0,
    "Pedro Porro": 5.5,
    "David Raya": 5.5,
    "Alisson Becker": 5.5,
    "Ederson": 5.5,
    "Emiliano Martínez": 5.5,
}

def calculate_price(full_name, pos, team_short):
    # 1. Check for Premium Override
    if full_name in premium_prices:
        return premium_prices[full_name]
    
    # 2. Dynamic generation based on Team Tier and Position
    # Using round(x * 2) / 2 ensures prices snap to .0 or .5
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
        content = f.read()
except FileNotFoundError:
    print("Error: PL.txt not found.")
    exit()

print("Parsing PL.txt and assigning dynamic FPL pricing...")

content = re.sub(r'\n\\s*', ' ', content)
content = re.sub(r'\\s*', '', content)

pos_map = {'G': 'GK', 'D': 'DEF', 'M': 'MID', 'F': 'FWD'}

current_team = None
parsing_players = False
player_count = 0

for line in content.split('\n'):
    line = line.strip()
    if not line:
        continue

    if line in teams_data:
        short_name, stadium, founded, primary, secondary = teams_data[line]
        current_team, _ = Team.objects.get_or_create(
            name=line,
            defaults={'short_name': short_name, 'stadium': stadium, 'founded_year': founded, 'primary_color': primary, 'secondary_color': secondary}
        )
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
            if not num_str.isdigit():
                continue

            full_name = parts[1].strip()
            if not full_name:
                continue

            name_parts = full_name.split(' ')
            if len(name_parts) > 1:
                first_name = name_parts[0]
                last_name = ' '.join(name_parts[1:])
            else:
                first_name = ''
                last_name = name_parts[0]

            pos_char = parts[3].strip()
            pos = pos_map.get(pos_char, 'MID')
            
            # Generate the realistic price!
            price = calculate_price(full_name, pos, current_team.short_name)

            Player.objects.create(
                team=current_team,
                first_name=first_name,
                last_name=last_name,
                position=pos,
                price=price,
                is_active=True
            )
            player_count += 1

print(f"Successfully imported {player_count} active players with dynamic pricing!")

print("Creating gameweeks...")
gw_data = [
    (29, '2026-02-22 11:00', False), (30, '2026-03-08 11:00', False), (31, '2026-03-15 11:00', False),
    (32, '2026-03-29 11:00', True), (33, '2026-04-05 11:00', False), (34, '2026-04-19 11:00', False),
]
for number, deadline_str, is_active in gw_data:
    Gameweek.objects.create(number=number, deadline=datetime.strptime(deadline_str, '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc), is_active=is_active)

print("Setup Complete!")
