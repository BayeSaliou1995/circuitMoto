# -*- coding: utf-8 -*-
"""Statistiques détaillées du back-office."""
from __future__ import annotations

from datetime import date

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.shortcuts import render
from django.utils import timezone

from ..models import Circuit, Document, Inscription, Paiement, Personne, StatutInscription


def _first_day_of_month(d: date) -> date:
    return date(d.year, d.month, 1)


def _add_month(d: date) -> date:
    return date(d.year + (1 if d.month == 12 else 0), 1 if d.month == 12 else d.month + 1, 1)


def _sub_months(d: date, n: int) -> date:
    y = d.year
    m = d.month - n
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


@staff_member_required
def stats(request):
    today = timezone.now().date()
    default_end = _first_day_of_month(today)
    default_start = _sub_months(default_end, 11)
    try:
        start_q = request.GET.get("start")
        end_q = request.GET.get("end")
        start = date.fromisoformat(start_q + "-01") if start_q and len(start_q) == 7 else date.fromisoformat(start_q) if start_q else default_start
        end = date.fromisoformat(end_q + "-01") if end_q and len(end_q) == 7 else date.fromisoformat(end_q) if end_q else default_end
    except Exception:
        start, end = default_start, default_end
    start = _first_day_of_month(start)
    end = _first_day_of_month(end)

    months, keys = [], []
    cur = start
    while cur <= end:
        months.append(cur.strftime("%b %Y").capitalize())
        keys.append(cur.strftime("%Y-%m"))
        cur = _add_month(cur)

    total_circuits = Circuit.objects.count()
    total_personnes = Personne.objects.count()
    total_inscriptions = Inscription.objects.count()
    total_validees = Inscription.objects.filter(statut=StatutInscription.VALIDE).count()
    total_attendu = Paiement.objects.aggregate(s=Coalesce(Sum("montant_du"), 0))["s"]
    total_encaisse = Paiement.objects.aggregate(s=Coalesce(Sum("montant_encaisse"), 0))["s"]
    taux_encaissement = int(round((total_encaisse / total_attendu) * 100)) if total_attendu else 0

    ins_series = Inscription.objects.filter(cree_le__date__gte=start, cree_le__date__lt=_add_month(end)).annotate(m=TruncMonth("cree_le")).values("m").annotate(c=Count("id")).order_by("m")
    ins_map = {row["m"].strftime("%Y-%m"): row["c"] for row in ins_series}
    due_series = Paiement.objects.filter(echeance_le__gte=start, echeance_le__lt=_add_month(end)).annotate(m=TruncMonth("echeance_le")).values("m").annotate(s=Coalesce(Sum("montant_du"), 0)).order_by("m")
    due_map = {row["m"].strftime("%Y-%m"): row["s"] for row in due_series}
    paid_series = Paiement.objects.filter(encaisse_le__isnull=False, encaisse_le__gte=start, encaisse_le__lt=_add_month(end)).annotate(m=TruncMonth("encaisse_le")).values("m").annotate(s=Coalesce(Sum("montant_encaisse"), 0)).order_by("m")
    paid_map = {row["m"].strftime("%Y-%m"): row["s"] for row in paid_series}
    serie_ins = [ins_map.get(k, 0) for k in keys]
    serie_due = [due_map.get(k, 0) for k in keys]
    serie_paid = [paid_map.get(k, 0) for k in keys]

    rep_ins = list(Inscription.objects.values("statut").annotate(c=Count("id")).order_by("statut"))
    rep_docs = list(Document.objects.values("statut").annotate(c=Count("id")).order_by("statut"))
    rep_circuits = list(Circuit.objects.values("statut").annotate(c=Count("id")).order_by("statut"))

    upcoming = Circuit.objects.filter(date_debut__gte=today).annotate(nb=Count("inscriptions")).order_by("date_debut")[:10]
    upcoming_ctx = []
    for c in upcoming:
        cap = c.capacite or 0
        pct = int(round((c.nb / cap) * 100)) if cap else 0
        upcoming_ctx.append({
            "id": c.id,
            "nom": c.nom,
            "code": c.code,
            "date_debut": c.date_debut.isoformat(),
            "capacite": cap,
            "nb": c.nb,
            "pct": pct,
        })

    people_series = Personne.objects.filter(cree_le__date__gte=start, cree_le__date__lt=_add_month(end)).annotate(m=TruncMonth("cree_le")).values("m").annotate(c=Count("id")).order_by("m")
    people_map = {row["m"].strftime("%Y-%m"): row["c"] for row in people_series}
    serie_people = [people_map.get(k, 0) for k in keys]

    data = {
        "range": {"start": start.isoformat(), "end": end.isoformat(), "labels": months, "keys": keys},
        "kpis": {
            "circuits": total_circuits,
            "personnes": total_personnes,
            "inscriptions": total_inscriptions,
            "validees": total_validees,
            "attendu": total_attendu,
            "encaisse": total_encaisse,
            "taux": taux_encaissement,
        },
        "series": {
            "inscriptions": serie_ins,
            "attendu": serie_due,
            "encaisse": serie_paid,
            "personnes": serie_people,
        },
        "repartitions": {"inscriptions": rep_ins, "documents": rep_docs, "circuits": rep_circuits},
        "upcoming": upcoming_ctx,
    }
    return render(request, "circuitMoto/admin/stats.html", {"data": data, "start": start, "end": end})
