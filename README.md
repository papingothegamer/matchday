# MatchDay — Premier League Fantasy Simulator

MatchDay is a fully-featured, Django-based Fantasy Football application complete with a simulated Match Engine, dynamic player economy, and competitive mini-leagues.

## Development Roadmap & Features

### Phase 1: Foundation & Authentication
- Custom Django Models for Teams, Players, Gameweeks, Matches, and PlayerStats.
- Robust user registration, login, and Administrator firewall modes.
- Dark-themed, minimalist UI established across base templates.

### Phase 2: Real-World Data Integration
- Automated `populate_pl.py` script bridging real-world Premier League data (teams, crests, player rosters) into the Django database.
- Scalable database schema supporting over 1,000 active players.

### Phase 3: The Match Engine
- Automated `simulation.py` and scheduling system.
- Randomized match score simulations utilizing weighted team strength variables.
- Individual player stat generation (Goals, Assists, Clean Sheets, Yellow/Red Cards) tying directly into standard FPL point calculations.

### Phase 4: Leaderboards & Mini-Leagues
- Dynamic Global Leaderboard tracking top points, goals, and assists.
- Competitive Mini-League system using secure, randomly generated 8-character Share Codes.
- Automatic aggregation of user team history for season-long standings.

### Phase 5: Manager Hub & Notifications
- Manager Profile page featuring an interactive, CSS-animated Gameweek History Bar Chart.
- AJAX-powered Notification Dropdown system alerting managers of simulation updates and deadlines.
- Responsive, native-app style mobile navigation and routing.

### Phase 6: The Transfer Market & Economy
- Distinct UI separation between "Squad Management" and "Transfer Market" modes.
- Enforcement of a strict £100.0m salary cap.
- **Dynamic Pricing Engine:** Player prices algorithmically rise (+£0.1m) or fall (-£0.1m) based on gameweek performance.
- **Transfer Ledger:** Tracking of 1 Free Transfer per week, deducting -4 points for excessive transfers, and calculating the classic 50% profit tax upon player sale.

## Technical Stack
* **Backend:** Python / Django
* **Database:** SQLite (dev)
* **Frontend:** HTML5 / Vanilla JavaScript / Pure CSS (No external frameworks)
