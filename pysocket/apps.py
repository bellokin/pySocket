# pysocket/apps.py
try:
    from django.apps import AppConfig
    
    class PysocketConfig(AppConfig):
        default_auto_field = 'django.db.models.BigAutoField'
        name = 'pysocket'

        def ready(self):
            # Import signals or other startup code
            pass

except ImportError:
    # Django is not installed, provide dummy implementation
    class PysocketConfig:
        pass