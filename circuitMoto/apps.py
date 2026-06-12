# circuitMoto/apps.py
from django.apps import AppConfig

class CircuitMotoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "circuitMoto"
    verbose_name = "Circuit Moto"

    def ready(self):
        # Enregistre les champs traduits
        from . import translation  # noqa
