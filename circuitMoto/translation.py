# circuitMoto/translation.py
from modeltranslation.translator import register, TranslationOptions
from .models import Circuit, OptionCircuit

@register(Circuit)
class CircuitTR(TranslationOptions):
    fields = (
        "nom", "description", "infos_rdv",
        "programme", "kilometrages",
        "prix_comprend", "prix_ne_comprend_pas",
        "echeancier_texte",
    )

@register(OptionCircuit)
class OptionCircuitTR(TranslationOptions):
    fields = ("intitule", "description")
