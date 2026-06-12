# circuitMoto/signals.py
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.conf import settings

from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Circuit, OptionCircuit

from .models import PasswordHistory

User = get_user_model()

@receiver(pre_save, sender=User)
def keep_old_password_in_history(sender, instance: User, **kwargs):
    """
    Avant de sauvegarder le User, si le password change, on pousse l'ancien hash en historique.
    """
    if not instance.pk:
        return  # création: pas d'historique à stocker
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    # password modifié ?
    if old.password and old.password != instance.password:
        PasswordHistory.objects.create(user=instance, encoded=old.password)
        # purge au-delà du quota
        keep = int(getattr(settings, "PASSWORD_HISTORY_SIZE", 5))
        qs = PasswordHistory.objects.filter(user=instance).order_by("-created_at")
        ids_to_delete = list(qs.values_list("id", flat=True))[keep:]
        if ids_to_delete:
            PasswordHistory.objects.filter(id__in=ids_to_delete).delete()

def fill_en_from_fr(instance, fields):
    for f in fields:
        fr = getattr(instance, f"{f}_fr", "") or getattr(instance, f, "")
        en = getattr(instance, f"{f}_en", "")
        if fr and not en:
            setattr(instance, f"{f}_en", fr)

@receiver(pre_save, sender=Circuit)
def circuit_autofill_en(sender, instance, **kwargs):
    fill_en_from_fr(instance, [
        "nom","description","infos_rdv","programme","kilometrages",
        "prix_comprend","prix_ne_comprend_pas","echeancier_texte"
    ])

@receiver(pre_save, sender=OptionCircuit)
def option_autofill_en(sender, instance, **kwargs):
    fill_en_from_fr(instance, ["intitule","description"])

