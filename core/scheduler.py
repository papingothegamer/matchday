from apscheduler.schedulers.background import BackgroundScheduler
from django.utils import timezone


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(_check_and_simulate, 'interval', minutes=30, id='gw_simulator', replace_existing=True)
    scheduler.start()
    print('MatchDay scheduler started.')


def _check_and_simulate():
    from core.models import Gameweek
    from core.simulation import simulate_gameweek
    now = timezone.now()
    active_gw = Gameweek.objects.filter(is_active=True).first()
    if active_gw and now >= active_gw.deadline:
        print(f'Deadline passed for GW{active_gw.number} — running simulation...')
        simulate_gameweek(active_gw.number)
