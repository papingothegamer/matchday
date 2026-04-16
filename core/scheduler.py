import time
import threading
from django.utils import timezone
from django.core.management import call_command
import sys

def run_auto_engine():
    from core.models import Gameweek
    while True:
        try:
            # Find active Gameweek
            active_gw = Gameweek.objects.filter(is_active=True).first()
            
            # Check deadline
            if active_gw and active_gw.deadline:
                if timezone.now() >= active_gw.deadline:
                    print(f"\n⏰ [AUTO-ENGINE] Deadline passed for GW{active_gw.number}!")
                    print(f"🤖 [AUTO-ENGINE] Taking control. Initiating Master Process...")
                    call_command('process_gameweek')
        except Exception as e:
            print(f"❌ [AUTO-ENGINE] Error: {e}")
            
        time.sleep(60)

def start_scheduler():
    if 'runserver' in sys.argv:
        if os.environ.get('RUN_MAIN') == 'true':
            thread = threading.Thread(target=run_auto_engine, daemon=True)
            thread.start()
            print("🤖 MatchDay Auto-Engine activated. Monitoring Gameweek deadlines...")
