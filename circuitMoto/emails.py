# circuitMoto/emails.py
# -*- coding: utf-8 -*-
from typing import Optional, List
import logging

from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import urlencode
from django.http import HttpRequest
from .models import SitePrefs

logger = logging.getLogger(__name__)


# ============================================================================
# Helpers généraux (inchangés)
# ============================================================================

def _abs_url(path: str) -> str:
    base = getattr(settings, "SITE_URL", "") or ""
    return f"{base}{path}"


def _get_email_flags():
    key = "site_email_flags_v1"
    flags = cache.get(key)
    if flags is None:
        flags = SitePrefs.as_flags()
        cache.set(key, flags, 30)  # 30s suffit
    return flags


def _emails_paused_for(role: str) -> bool:
    flags = _get_email_flags()
    if flags.get("all"):
        return True
    if role == "pilote" and flags.get("pilote"):
        return True
    if role == "passager" and flags.get("passager"):
        return True
    return False


def _send(
    to_email: str,
    subject: str,
    template_base: str,
    ctx: dict,
    *,
    bcc_admin: bool = False,
    reply_to=None,
    role: Optional[str] = None
):
    """
    Envoi email txt+html à partir de templates:
      templates/emails/<template_base>.txt
      templates/emails/<template_base>.html
    """
    if not to_email:
        return 0

    if role and _emails_paused_for(role):
        logger.info("✉️  Envoi email PAUSÉ (%s) — %s", role, subject)
        return 0

    text_body = render_to_string(f"emails/{template_base}.txt", ctx)
    html_body = render_to_string(f"emails/{template_base}.html", ctx)

    admin_email = getattr(settings, "NOTIFY_ADMIN_EMAIL", settings.DEFAULT_FROM_EMAIL)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
        bcc=[admin_email] if bcc_admin else None,
        reply_to=reply_to or None,
    )
    msg.attach_alternative(html_body, "text/html")
    return msg.send(fail_silently=False)


# ============================================================================
# ✅ Spécifique : blocs dynamiques de l'email "inscription validée"
# ============================================================================

DEFAULT_RDV_TEXT = (
    "Départ depuis la station Total (Walin, près de Namur ou Luxembourg suivant le programme) "
    "en direction du Luxembourg."
)

DEFAULT_ORGA_TEXT = (
    "Le circuit se déroule en autonomie (avec ta trace GPS).\n"
    "Des groupes se formeront naturellement en fonction des affinités et du rythme de chacun.\n"
    "La réunion pré-voyage sera également l’occasion de rencontrer les autres participants."
)

DEFAULT_CHECKLIST = [
    "Carte d’identité",
    "Permis de conduire",
    "Mini-trousse de secours : Imodium, Primperan/Motilium, Dafalgan, Ercéfuryl",
    "Protection solaire",
    "Baume pour les lèvres",
    "Bouchons d’oreilles",
]


def _clean_lines(text: str) -> List[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def _build_validee_dynamic_blocks(circuit):
    """
    Retourne:
      rdv_text: str
      organisation_text: str
      checklist_items: list[str]
    En prenant les overrides Circuit.email_* si présents, sinon fallback default.
    """
    rdv_text = (getattr(circuit, "email_rdv", "") or "").strip() or DEFAULT_RDV_TEXT
    organisation_text = (getattr(circuit, "email_organisation", "") or "").strip() or DEFAULT_ORGA_TEXT

    custom_check = _clean_lines(getattr(circuit, "email_checklist", "") or "")
    checklist_items = custom_check if custom_check else DEFAULT_CHECKLIST

    return rdv_text, organisation_text, checklist_items


# ============================================================================
# Notifs (tes fonctions existantes, conservées)
# ============================================================================

def notify_inscription_recue(ins):
    ctx = {
        "ins": ins,
        "edit_url": _abs_url(reverse("inscription_edit_start", args=[ins.id_public])),

        "ins_detail_admin_url": _abs_url(
            f"{reverse('bo_inscription_list')}?{urlencode({'q': str(ins.id_public)})}"
        ),

        "personne_admin_url": _abs_url(reverse("bo_personne_detail", args=[ins.pilote_id])),

        "passager_admin_url": (
            _abs_url(reverse("bo_personne_detail", args=[ins.passager_id]))
            if ins.passager_id else ""
        ),

        "infos_paiement": (getattr(ins.circuit, "infos_paiement", "") or "").strip(),
        "has_infos_paiement": bool((getattr(ins.circuit, "infos_paiement", "") or "").strip()),
        "paiement_libelle": "Virement bancaire",
    }

    subj = f"[{ins.circuit.code}] Inscription bien reçue – {ins.pilote.prenom} {ins.pilote.nom}"

    _send(ins.pilote.email, subj, "inscription_recue", ctx, role="pilote")

    if ins.passager and ins.passager.email:
        _send(ins.passager.email, subj, "inscription_recue_passager", ctx, role="passager")

    admin_email = getattr(settings, "NOTIFY_ADMIN_EMAIL", settings.DEFAULT_FROM_EMAIL)

    _send(
        admin_email,
        f"Nouvelle inscription reçue – {ins.circuit.nom}",
        "inscription_recue_admin",
        ctx
    )


def notify_inscription_validee(ins):
    """
    ✅ Mise à jour ici uniquement:
    - Ajoute rdv_text / organisation_text / checklist_items
    - Conserve tout le reste (dates, edit_url, flags, etc.)
    """
    c = ins.circuit

    rdv_text, organisation_text, checklist_items = _build_validee_dynamic_blocks(c)

    # Contexte enrichi (tout depuis le circuit / l’inscription)
    ctx_base = {
        "ins": ins,
        "c": c,
        "edit_url": _abs_url(reverse("inscription_edit_start", args=[ins.id_public])),
        "option_expire_le": getattr(ins, "option_expire_le", None),
        "delai_option": getattr(c, "delai_option_jours", None),

        "circuit_dates": (
            f"{c.date_debut:%d/%m/%Y} → {c.date_fin:%d/%m/%Y}"
            if getattr(c, "date_debut", None) and getattr(c, "date_fin", None) else ""
        ),

        # ✅ blocs dynamiques utilisés par le template inscription_validee
        "rdv_text": rdv_text,
        "organisation_text": organisation_text,
        "checklist_items": checklist_items,

        "infos_paiement": (getattr(c, "infos_paiement", "") or "").strip(),
        "has_infos_paiement": bool((getattr(c, "infos_paiement", "") or "").strip()),
        "paiement_libelle": "Virement bancaire",
    }

    subj = f"[{c.code}] Confirmation d’inscription – {ins.pilote.prenom} {ins.pilote.nom}"

    # Pilote (PAUSABLE)
    _send(
        ins.pilote.email,
        subj,
        "inscription_validee",
        {**ctx_base, "dest_name": (ins.pilote.prenom or ins.pilote.nom or "aventurier"), "role": "pilote"},
        role="pilote",
    )

    # Passager (si présent – PAUSABLE aussi)
    if ins.passager and ins.passager.email:
        _send(
            ins.passager.email,
            subj,
            "inscription_validee",
            {**ctx_base, "dest_name": (ins.passager.prenom or ins.passager.nom or "aventurier"), "role": "passager"},
            role="passager",
        )


def notify_document_refuse(doc):
    # Ce mail continue d’être envoyé au pilote (important opérationnel)
    ins = doc.inscription
    ctx = {
        "ins": ins,
        "doc": doc,
        "upload_url": _abs_url(
            reverse("inscription_edit_start", args=[ins.id_public]) + "?step=documents"
        ),
        "raison": (doc.note or "").strip(),
    }
    subj = f"[{ins.circuit.code}] Document refusé – {doc.get_type_document_display()}"
    _send(ins.pilote.email, subj, "document_refuse", ctx)

from decimal import Decimal


def _fmt_money(value):
    try:
        return f"{Decimal(value or 0):.2f}"
    except Exception:
        return "0.00"


def notify_paiement_resume(ins, recipient, *, recipient_role="pilote"):
    """
    Envoie un récapitulatif de situation de paiement pour une inscription.
    recipient: Personne cible (pilote ou passager)
    """

    paiements = list(ins.paiements.all().order_by("echeance_le", "pk"))

    total_paye = sum((p.montant_encaisse or 0) for p in paiements)
    total_attendu = (
        (ins.prix_pilote_unitaire or 0)
        + ((ins.prix_passager_unitaire or 0) if ins.passager_id else 0)
        + sum(sel.prix_total() for sel in ins.selections_options.all())
    )

    difference = (total_paye or 0) - (total_attendu or 0)
    reste_a_payer = max((total_attendu or 0) - (total_paye or 0), 0)
    trop_percu = max((total_paye or 0) - (total_attendu or 0), 0)

    situation = "solde"
    if reste_a_payer > 0:
        situation = "reste"
    elif trop_percu > 0:
        situation = "trop_percu"

    ctx = {
        "ins": ins,
        "recipient": recipient,
        "dest_name": (recipient.prenom or recipient.nom or "client"),
        "circuit": ins.circuit,
        "paiements": paiements,
        "total_attendu": total_attendu,
        "total_paye": total_paye,
        "reste_a_payer": reste_a_payer,
        "trop_percu": trop_percu,
        "difference": difference,
        "situation": situation,
        "edit_url": _abs_url(reverse("inscription_edit_start", args=[ins.id_public])),
        "infos_paiement": (getattr(ins.circuit, "infos_paiement", "") or "").strip(),
        "has_infos_paiement": bool((getattr(ins.circuit, "infos_paiement", "") or "").strip()),
        "paiement_libelle": "Virement bancaire",
        "total_attendu_fmt": _fmt_money(total_attendu),
        "total_paye_fmt": _fmt_money(total_paye),
        "reste_a_payer_fmt": _fmt_money(reste_a_payer),
        "trop_percu_fmt": _fmt_money(trop_percu),
    }

    subject = f"[{ins.circuit.code}] Point sur votre paiement – {ins.circuit.nom}"

    return _send(
        recipient.email,
        subject,
        "paiement_resume",
        ctx,
        role=recipient_role,
    )

def notify_paiement_resume_compose(*, recipient_email: str, subject: str, ctx: dict, role: str = "pilote"):
    return _send(
        recipient_email,
        subject,
        "paiement_resume_compose",
        ctx,
        role=role,
    )

def notify_demande_balades_admin(demande, request: Optional[HttpRequest] = None):
    admin_email = getattr(settings, "NOTIFY_ADMIN_EMAIL", settings.DEFAULT_FROM_EMAIL)

    selected_balades = list(demande.balades.all().order_by("date_debut", "ordre", "titre"))

    site_url = getattr(settings, "SITE_URL", "")
    if not site_url and request is not None:
        site_url = request.build_absolute_uri("/").rstrip("/")

    ctx = {
        "demande": demande,
        "selected_balades": selected_balades,
        "site_url": site_url,
    }

    subject = f"[Balades 1 jour] Nouvelle sélection — {demande.prenom} {demande.nom}"
    return _send(
        admin_email,
        subject,
        "balades_demande_admin",
        ctx,
        bcc_admin=False,
        reply_to=[demande.email] if demande.email else None,
        role=None,
    )


def notify_demande_balades_user_ack(demande, request: Optional[HttpRequest] = None):
    selected_balades = list(demande.balades.all().order_by("date_debut", "ordre", "titre"))

    site_url = getattr(settings, "SITE_URL", "")
    if not site_url and request is not None:
        site_url = request.build_absolute_uri("/").rstrip("/")

    ctx = {
        "demande": demande,
        "selected_balades": selected_balades,
        "site_url": site_url,
    }

    subject = "Votre sélection de balades a bien été reçue"
    return _send(
        demande.email,
        subject,
        "balades_demande_user_ack",
        ctx,
        bcc_admin=False,
        role=None,
    )


def notify_programme_2027_admin(demande, request: Optional[HttpRequest] = None):
    admin_email = getattr(settings, "NOTIFY_ADMIN_EMAIL", settings.DEFAULT_FROM_EMAIL)
    selections = list(
        demande.selections
        .select_related("circuit")
        .order_by("circuit__ordre", "circuit__titre")
    )

    site_url = getattr(settings, "SITE_URL", "")
    if not site_url and request is not None:
        site_url = request.build_absolute_uri("/").rstrip("/")

    detail_url = ""
    try:
        detail_url = _abs_url(f"{reverse('bo_programme_2027_interests')}?q={demande.email}")
    except Exception:
        detail_url = site_url

    ctx = {
        "demande": demande,
        "selections": selections,
        "site_url": site_url,
        "detail_url": detail_url,
    }

    subject = f"[Pre Programme 2027] Nouvel interesse - {demande.prenom} {demande.nom}"
    return _send(
        admin_email,
        subject,
        "programme_2027_interest_admin",
        ctx,
        bcc_admin=False,
        reply_to=[demande.email] if demande.email else None,
        role=None,
    )


def notify_programme_2027_user_ack(demande, request: Optional[HttpRequest] = None):
    selections = list(
        demande.selections
        .select_related("circuit")
        .order_by("circuit__ordre", "circuit__titre")
    )

    site_url = getattr(settings, "SITE_URL", "")
    if not site_url and request is not None:
        site_url = request.build_absolute_uri("/").rstrip("/")

    ctx = {
        "demande": demande,
        "selections": selections,
        "site_url": site_url,
    }

    subject = "Votre interet pour le pre programme 2027 a bien ete recu"
    return _send(
        demande.email,
        subject,
        "programme_2027_interest_user_ack",
        ctx,
        bcc_admin=False,
        role=None,
    )
