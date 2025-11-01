from django.apps import AppConfig


class CappConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "capp"

    def ready(self):
        import capp.signals
