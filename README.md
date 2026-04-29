# MatchDay: Full-Stack Fantasy Simulation Engine

MatchDay is a comprehensive web application built with Django that merges a realistic football simulation engine with an interactive fantasy management dashboard.

## 🔗 Video Demonstration
**[INSERT YOUR YOUTUBE/GOOGLE DRIVE VIDEO LINK HERE]**

## 🚀 Quick Start (How to Run)
1. Clone the repository and navigate to the project directory.
2. Create a virtual environment: `python -m venv venv` and activate it.
3. Install dependencies: `pip install -r requirements.txt`
4. Apply database migrations: `python manage.py migrate`
5. *(Optional) Run `python populate_pl.py` to seed the database with real teams.*
6. Start the server: `python manage.py runserver`

## 🧠 Core Methodology & Architecture
This project utilizes the **MVT (Model-View-Template)** architecture to separate database logic from the frontend UI.
* **Backend:** Python/Django handles the simulation algorithms, relational data integrity, and strict payload validation (e.g., preventing budget exploits).
* **Database:** SQLite with a highly relational structure (`Teams` -> `Players` -> `Matches` -> `PlayerStats` -> `FantasyPicks` -> `User`).
* **Frontend:** Vanilla JavaScript and the Fetch API (AJAX) drive a dynamic, SPA-like experience without heavy frameworks. Chart.js is used for data visualization.

## ⚙️ Key Engine Features
### 1. The Simulation Algorithm (`simulation.py`)
Unlike apps with static data, MatchDay features a background algorithmic heuristic engine. When a Gameweek rolls over, the engine simulates 10 matches using weighted randomization, realistically distributes player minutes (including substitutions and injuries), assigns match events (goals/assists), and calculates official FPL points.

### 2. Strict State Management (Pick Team)
The application enforces strict economic and state rules. Users are capped at a £100.0m budget and a 15-player squad limit. The backend calculates dynamic player depreciation and validates all API payloads to prevent client-side manipulation or budget exploits.

### 3. Dynamic Data Aggregation (Global Hubs)
The system aggregates simulated data on the fly. The **Fixtures Hub** calculates a live 20-team Premier League standings table based purely on the background engine's match results, while the **Leaderboard** aggregates global user points dynamically using Django's ORM `Sum` and `annotate` functions.
