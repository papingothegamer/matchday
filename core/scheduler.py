import os
import time
import threading
from django.utils import timezone
from django.core.management import call_command
import sys

def run_auto_engine():
    from core.models import Gameweek, Match
    while True:
        try:
            # Find active Gameweek
            active_gw = Gameweek.objects.filter(is_active=True).first()
            
            if active_gw:
                # 1. Staggered Simulation: Play matches whose time has come
                pending_matches = Match.objects.filter(
                    gameweek=active_gw, 
                    is_played=False, 
                    match_date__lte=timezone.now()
                )
                
                if pending_matches.exists():
                    from core.simulation import simulate_match
                    for match in pending_matches:
                        print(f"[AUTO-ENGINE] KICKOFF: {match.home_team.short_name} vs {match.away_team.short_name}")
                        simulate_match(match)
                        time.sleep(2) # Slight delay for immersion in logs
                    
                    # After matches are played, trigger a "partial" point calculation if needed
                    # simulate_gameweek is heavy, but let's assume it runs in rollover mostly.
                    # Or we can run it here to keep dashboard updated.
                    from core.simulation import simulate_gameweek
                    simulate_gameweek(active_gw)

                # 2. Conditional Rollover: Only if deadline passed AND all matches played
                if active_gw.deadline and timezone.now() >= active_gw.deadline:
                    unplayed_count = Match.objects.filter(gameweek=active_gw, is_played=False).count()
                    
                    if unplayed_count == 0:
                        # Wait a buffer period (e.g. 1 hour) after last match before rollover
                        # For demo purposes, we'll do it immediately
                        print(f"\n[AUTO-ENGINE] GW{active_gw.number} complete. Initiating Rollover...")
                        call_command('process_gameweek')
                    else:
                        if int(time.time()) % 300 < 60: # Log every ~5 mins
                            print(f"[AUTO-ENGINE] GW{active_gw.number} in progress. Waiting for {unplayed_count} matches.")

        except Exception as e:
            print(f"[AUTO-ENGINE] Error: {e}")
            
        time.sleep(60)

def start_scheduler():
    if 'runserver' in sys.argv:
        if os.environ.get('RUN_MAIN') == 'true':
            thread = threading.Thread(target=run_auto_engine, daemon=True)
            thread.start()
            print("MatchDay Auto-Engine activated. Monitoring Gameweek deadlines...")
