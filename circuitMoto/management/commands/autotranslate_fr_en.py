# circuitMoto/management/commands/autotranslate_fr_en.py
from django.core.management.base import BaseCommand
from circuitMoto.models import Circuit, OptionCircuit
from circuitMoto.translation_utils import auto_translate_instance

AUTO_FIELDS_CIRCUIT = (
    "nom", "description", "infos_rdv",
    "programme", "kilometrages",
    "prix_comprend", "prix_ne_comprend_pas",
    "echeancier_texte",
)
AUTO_FIELDS_OPTION = ("intitule", "description")

class Command(BaseCommand):
    help = "Auto-traduit FR → EN pour Circuit et OptionCircuit (ne remplace pas l'EN si déjà anglais)."

    def handle(self, *args, **opts):
        c_upd = o_upd = 0
        for c in Circuit.objects.all():
            if auto_translate_instance(c, AUTO_FIELDS_CIRCUIT):
                c.save()
                c_upd += 1
        for o in OptionCircuit.objects.all():
            if auto_translate_instance(o, AUTO_FIELDS_OPTION):
                o.save()
                o_upd += 1
        self.stdout.write(self.style.SUCCESS(f"Circuits mis à jour: {c_upd}"))
        self.stdout.write(self.style.SUCCESS(f"Options mises à jour: {o_upd}"))