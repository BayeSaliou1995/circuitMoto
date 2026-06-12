# -*- coding: utf-8 -*-
"""Helpers transverses du back-office."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.http import JsonResponse

from ..models import LibellePaiement


def is_ajax(request) -> bool:
    """Retourne True si la requête est une requête AJAX."""
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def json_ok(message: str = "", **payload):
    """Réponse JSON de succès uniforme."""
    return JsonResponse({"ok": True, "message": message, **payload})


def json_err(message: str = "Erreur inconnue", status: int = 400, **payload):
    """Réponse JSON d'erreur uniforme."""
    return JsonResponse({"ok": False, "message": message, **payload}, status=status)


def ordered_payments_for_display(ins):
    """Retourne les paiements dans un ordre métier stable pour l'UI et les emails.

    Ordre souhaité : ACOMPTE1 → ACOMPTE2 → SOLDE → AUTRE.
    """
    order_map = {
        LibellePaiement.ACOMPTE1: 1,
        LibellePaiement.ACOMPTE2: 2,
        LibellePaiement.SOLDE: 3,
        LibellePaiement.AUTRE: 4,
    }
    paiements = list(ins.paiements.all())
    paiements.sort(
        key=lambda p: (
            order_map.get(p.libelle, 99),
            p.echeance_le or date.max,
            p.pk,
        )
    )
    return paiements


def decimal_or_zero(value) -> Decimal:
    return Decimal(value or 0)
