# circuitMoto/context_processors.py
from .models import SitePrefs, Circuit
from django.utils.timezone import now
from django.conf import settings

def site_prefs(request):
    site_url = getattr(settings, "SITE_URL", "https://pulsion-inscription.com").rstrip("/")
    return {"SITE_URL": site_url, "email_flags": SitePrefs.as_flags()}

def circuits_for_nav(request):
    today = now().date()
    qs = (Circuit.objects
          .filter(statut='PUBLIE', date_fin__gte=today)
          .only('id', 'code','nom','date_debut','date_fin')   # perf
          .order_by('date_debut'))   # ⬅️ plus de [:12]
    return {'circuits_nav': qs}
