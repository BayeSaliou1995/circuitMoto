# -*- coding: utf-8 -*-
"""Logique de lecture et d'imputation des paiements."""
from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from ..models import LibellePaiement, StatutPaiement
from .common import ordered_payments_for_display


def apply_manual_payments_to_inscription(
    ins,
    *,
    acompte1_amount=Decimal("0"),
    acompte2_amount=Decimal("0"),
    solde_amount=Decimal("0"),
    payment_date=None,
):
    """Met à jour les paiements sans mélanger les champs saisis dans le formulaire."""
    payment_date = payment_date or timezone.localdate()
    mapping = {
        LibellePaiement.ACOMPTE1: Decimal(acompte1_amount or 0),
        LibellePaiement.ACOMPTE2: Decimal(acompte2_amount or 0),
        LibellePaiement.SOLDE: Decimal(solde_amount or 0),
    }

    remaining_unallocated = Decimal("0")
    for libelle, amount in mapping.items():
        if amount <= 0:
            continue
        p = ins.paiements.filter(libelle=libelle).first()
        if not p:
            remaining_unallocated += amount
            continue
        attendu = Decimal(p.montant_du or 0)
        deja_encaisse = Decimal(p.montant_encaisse or 0)
        restant_sur_ligne = max(attendu - deja_encaisse, Decimal("0"))
        a_imputer = min(amount, restant_sur_ligne)
        surplus = max(amount - a_imputer, Decimal("0"))
        if a_imputer > 0:
            nouveau_total = deja_encaisse + a_imputer
            p.montant_encaisse = nouveau_total
            p.encaisse_le = payment_date
            if nouveau_total >= attendu and attendu > 0:
                p.statut = StatutPaiement.PAYE
            elif nouveau_total > 0:
                p.statut = StatutPaiement.PARTIEL
            else:
                p.statut = StatutPaiement.A_PAYER
            p.save(update_fields=["montant_encaisse", "encaisse_le", "statut", "modifie_le"])
        if surplus > 0:
            remaining_unallocated += surplus

    return ordered_payments_for_display(ins), remaining_unallocated


def build_payment_summary_defaults(ins, personne):
    """Construit les valeurs initiales du modal récap paiement sans modifier la base."""
    paiements = ordered_payments_for_display(ins)
    total_attendu_courant = Decimal(
        (ins.prix_pilote_unitaire or 0)
        + ((ins.prix_passager_unitaire or 0) if ins.passager_id else 0)
        + sum(sel.prix_total() for sel in ins.selections_options.all())
    )
    total_deja_paye = Decimal(sum((p.montant_encaisse or 0) for p in paiements))
    montant_restant = max(total_attendu_courant - total_deja_paye, Decimal("0"))
    trop_percu = max(total_deja_paye - total_attendu_courant, Decimal("0"))
    situation_label = "Reste à payer" if montant_restant > 0 else "Trop-perçu" if trop_percu > 0 else "Soldé"

    recipient_role = "passager" if ins.passager_id == personne.pk else "pilote"
    recipient = ins.passager if recipient_role == "passager" else ins.pilote

    acompte1_val = Decimal("0")
    acompte2_val = Decimal("0")
    solde_val = Decimal("0")
    for p in paiements:
        encaisse = Decimal(p.montant_encaisse or 0)
        if p.libelle == LibellePaiement.ACOMPTE1:
            acompte1_val = encaisse
        elif p.libelle == LibellePaiement.ACOMPTE2:
            acompte2_val = encaisse
        elif p.libelle == LibellePaiement.SOLDE:
            solde_val = encaisse

    stored_options_added = Decimal(getattr(ins, "montant_options_ajoutees", 0) or 0)
    options_added = stored_options_added if stored_options_added > 0 else Decimal("0")
    if options_added > total_attendu_courant:
        options_added = Decimal("0")
    total_initial = total_attendu_courant - options_added if options_added > 0 else total_attendu_courant
    has_acompte1 = Decimal(ins.circuit.acompte1_par_personne or 0) > 0
    has_acompte2 = Decimal(ins.circuit.acompte2_par_personne or 0) > 0

    return {
        "ins_id": ins.pk,
        "recipient_role": recipient_role,
        "sujet": f"[{ins.circuit.code}] Point sur votre paiement – {ins.circuit.nom}",
        "intro_message": "Voici votre récapitulatif de paiement actuel concernant votre inscription.",
        "total_attendu": total_initial,
        "montant_options_ajoutees": options_added,
        "nouveau_total_attendu": total_attendu_courant,
        "acompte1_encaisse": acompte1_val,
        "acompte2_encaisse": acompte2_val,
        "solde_encaisse": solde_val,
        "paiement_recu_pour_options": Decimal(getattr(ins, "paiement_options_recu", 0) or 0),
        "date_paiement": timezone.localdate(),
        "montant_restant": montant_restant,
        "trop_percu": trop_percu,
        "situation_label": situation_label,
        "inclure_detail_paiements": True,
        "inclure_infos_paiement": True,
        "infos_paiement_custom": (getattr(ins.circuit, "infos_paiement", "") or "").strip(),
        "note_client": "",
        "recipient_email": getattr(recipient, "email", "") if recipient else "",
        "recipient_name": getattr(recipient, "nom_complet", "") if recipient else "",
        "paiements": paiements,
        "has_acompte1": has_acompte1,
        "has_acompte2": has_acompte2,
        "has_options_added": options_added > 0,
    }


def build_email_payment_rows(ins):
    """Construit les lignes de paiement pour les emails sans modifier la base."""
    rows = []
    for p in ordered_payments_for_display(ins):
        attendu = Decimal(p.montant_du or 0)
        encaisse = Decimal(p.montant_encaisse or 0)
        if encaisse >= attendu and attendu > 0:
            statut_label = "Payé"
        elif encaisse > 0:
            statut_label = "Partiellement payé"
        else:
            statut_label = "À payer"
        rows.append({
            "libelle": p.get_libelle_display(),
            "attendu": attendu,
            "encaisse": encaisse,
            "date": p.encaisse_le,
            "statut": statut_label,
        })
    return rows
