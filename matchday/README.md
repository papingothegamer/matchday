# MatchDay

A Premier League fantasy football app built with Django.  
Pick 11 players each gameweek, score points based on real match stats, compete on the leaderboard.

Built for the University of Lodz Application Servers course — also a personal portfolio project.

## Setup

```bash
# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py makemigrations core
python manage.py migrate

# Create a superuser
python manage.py createsuperuser

# Start the server
python manage.py runserver
```

## Access

- Home: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/

## Models

- `Team` — 20 Premier League clubs
- `Player` — squad players with position and price
- `Gameweek` — 38 gameweeks per season
- `Match` — fixtures with scores
- `PlayerStat` — per-match stats, auto-calculates fantasy points on save
- `FantasyTeam` — a user's picked team for a gameweek
- `FantasyPick` — individual player selections (through model)

## Scoring

| Event | Points |
|---|---|
| 90 min played | +2 |
| Goal (any) | +6 |
| Assist | +3 |
| Clean sheet (GK/DEF) | +4 |
| Clean sheet (MID) | +1 |
| Yellow card | -1 |
| Red card | -3 |

## Docs

See `docs/db_schema.html` for the full database schema and project plan.
