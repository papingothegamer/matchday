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
                        print(f"[AUTO-ENGINE] Simulating: {match}")
                        simulate_match(match)

                # 2. Conditional Rollover: Only if deadline passed AND all matches played
                if active_gw.deadline and timezone.now() >= active_gw.deadline:
                    unplayed_count = Match.objects.filter(gameweek=active_gw, is_played=False).count()
                    
                    if unplayed_count == 0:
                        print(f"\n[AUTO-ENGINE] GW{active_gw.number} finished! All matches played. Initiating Rollover...")
                        call_command('process_gameweek')
                    else:
                        # Optional: Log waiting status
                        pass 

        except Exception as e:
            print(f"[AUTO-ENGINE] Error: {e}")
            
        time.sleep(60)

def start_scheduler():
    if 'runserver' in sys.argv:
        if os.environ.get('RUN_MAIN') == 'true':
            thread = threading.Thread(target=run_auto_engine, daemon=True)
            thread.start()
            print("MatchDay Auto-Engine activated. Monitoring Gameweek deadlines...")
