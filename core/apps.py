from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from core.scheduler import start_scheduler
        import os
        if os.environ.get('RUN_MAIN') == 'true':
            start_scheduler()
