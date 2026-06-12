# circuitMoto/templatetags/circuits_nav.py
from django import template
from django.utils.timezone import now
from ..models import Circuit

register = template.Library()

@register.simple_tag
def upcoming_circuits(limit=None):
    today = now().date()
    qs = (Circuit.objects
          .filter(statut='PUBLIE', date_fin__gte=today)
          .only('id', 'code','nom','date_debut','date_fin')
          .order_by('date_debut'))

    # Si on passe 0, None ou "all" → illimité
    if limit in (None, 0, '0', 'all', 'ALL'):
        return qs
    try:
        n = int(limit)
        if n > 0:
            return qs[:n]
    except (TypeError, ValueError):
        pass
    return qs
