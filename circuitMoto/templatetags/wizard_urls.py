# circuitMoto/templatetags/wizard_urls.py
from django import template
from django.urls import reverse

register = template.Library()

@register.simple_tag(takes_context=True)
def wizard_step_url(context, step_name):
    """
    Renvoie l'URL du wizard pour un step donné, en EDIT si id_public présent,
    sinon en CREATE. Compatible avec SessionWizardView.
    """
    wizard = context.get('wizard')
    if wizard and getattr(wizard, "kwargs", None) and wizard.kwargs.get("id_public"):
        return reverse("inscription_edit_step", kwargs={
            "id_public": wizard.kwargs["id_public"],
            "step": step_name
        })
    # fallback création
    return reverse("inscription_create_step", kwargs={"step": step_name})
