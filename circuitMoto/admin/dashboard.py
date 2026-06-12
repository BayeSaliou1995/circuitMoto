# -*- coding: utf-8 -*-
"""Tableau de bord back-office."""
from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.utils import timezone

from ..models import Circuit, ContactMessage, Document, Inscription, NewsletterSubscriber, Paiement, Personne, StatutCircuit, StatutDocument, StatutInscription


@staff_member_required
def dashboard(request):
    now = timezone.localdate()
    recents_page = int(request.GET.get("recents_page", 1) or 1)
    docs_page = int(request.GET.get("docs_page", 1) or 1)
    contacts_page = int(request.GET.get("contacts_page", 1) or 1)
    newsletter_page = int(request.GET.get("newsletter_page", 1) or 1)
    ajax_section = (request.GET.get("section") or "").strip()

    nb_circuits = Circuit.objects.count()
    nb_circuits_a_venir = Circuit.objects.filter(date_debut__gte=now).count()
    nb_inscriptions = Inscription.objects.count()
    nb_inscriptions_validees = Inscription.objects.filter(statut=StatutInscription.VALIDE).count()
    nb_personnes = Personne.objects.count()
    nb_documents_attente = Document.objects.filter(statut=StatutDocument.EN_ATTENTE).count()
    nb_contacts_non_traites = ContactMessage.objects.filter(traite=False).count()
    nb_newsletter_total = NewsletterSubscriber.objects.count()
    nb_newsletter_active = NewsletterSubscriber.objects.filter(is_active=True).count()

    paiements_qs = Paiement.objects.all()
    total_attendu = paiements_qs.aggregate(v=Coalesce(Sum("montant_du"), 0))["v"] or 0
    total_encaisse = paiements_qs.aggregate(v=Coalesce(Sum("montant_encaisse"), 0))["v"] or 0
    total_restant = max((total_attendu or 0) - (total_encaisse or 0), 0)

    taux_validation = round((nb_inscriptions_validees / nb_inscriptions) * 100) if nb_inscriptions else 0
    taux_encaissement = round((total_encaisse / total_attendu) * 100) if total_attendu else 0

    prochains = Circuit.objects.filter(date_debut__gte=now, statut=StatutCircuit.PUBLIE).annotate(nb=Count("inscriptions")).order_by("date_debut")[:12]
    for c in prochains:
        cap = c.capacite or 0
        c.pct = int(round((c.nb / cap) * 100)) if cap else 0
        c.places_restantes = max(cap - c.nb, 0) if cap else 0
        c.est_bientot = bool(c.date_debut and (c.date_debut - now).days <= 15)

    base_circuits = Circuit.objects.annotate(nb=Count("inscriptions"))
    publies = base_circuits.filter(statut=StatutCircuit.PUBLIE).order_by("date_debut")[:8]
    archives = base_circuits.filter(statut=StatutCircuit.ARCHIVE).order_by("-date_debut")[:8]
    brouillons = base_circuits.filter(statut=StatutCircuit.BROUILLON).order_by("-modifie_le")[:8]

    inscriptions_recentes_qs = Inscription.objects.select_related("circuit", "pilote", "passager").order_by("-cree_le")
    inscriptions_recentes_page = Paginator(inscriptions_recentes_qs, 6).get_page(recents_page)
    documents_attente_qs = Document.objects.filter(statut=StatutDocument.EN_ATTENTE).select_related("inscription", "inscription__circuit", "inscription__pilote").order_by("cree_le")
    documents_attente_page = Paginator(documents_attente_qs, 6).get_page(docs_page)
    contacts_recents_qs = ContactMessage.objects.filter(traite=False).select_related("circuit").order_by("-cree_le")
    contacts_recents_page = Paginator(contacts_recents_qs, 6).get_page(contacts_page)
    newsletter_qs = NewsletterSubscriber.objects.order_by("-created_at", "-id")
    newsletter_page_obj = Paginator(newsletter_qs, 8).get_page(newsletter_page)

    circuits_complets = 0
    circuits_quasi_complets = 0
    circuits_upcoming_all = Circuit.objects.filter(date_debut__gte=now, statut=StatutCircuit.PUBLIE).annotate(nb=Count("inscriptions"))
    for c in circuits_upcoming_all:
        cap = c.capacite or 0
        if not cap:
            continue
        pct = (c.nb / cap) * 100
        if pct >= 100:
            circuits_complets += 1
        elif pct >= 80:
            circuits_quasi_complets += 1

    stats = {
        "nb_circuits": nb_circuits,
        "nb_circuits_a_venir": nb_circuits_a_venir,
        "nb_inscriptions": nb_inscriptions,
        "nb_inscriptions_validees": nb_inscriptions_validees,
        "nb_personnes": nb_personnes,
        "nb_documents_attente": nb_documents_attente,
        "nb_contacts_non_traites": nb_contacts_non_traites,
        "nb_newsletter_total": nb_newsletter_total,
        "nb_newsletter_active": nb_newsletter_active,
        "total_attendu": total_attendu,
        "total_encaisse": total_encaisse,
        "total_restant": total_restant,
        "taux_validation": taux_validation,
        "taux_encaissement": taux_encaissement,
        "circuits_complets": circuits_complets,
        "circuits_quasi_complets": circuits_quasi_complets,
    }

    if ajax_section == "recents":
        return render(request, "circuitMoto/admin/partials/dashboard/_inscriptions_recentes.html", {"inscriptions_recentes_page": inscriptions_recentes_page})
    if ajax_section == "documents":
        return render(request, "circuitMoto/admin/partials/dashboard/_documents_attente.html", {"documents_attente_page": documents_attente_page})
    if ajax_section == "contacts":
        return render(request, "circuitMoto/admin/partials/dashboard/_contacts_recents.html", {"contacts_recents_page": contacts_recents_page})
    if ajax_section == "newsletter":
        return render(request, "circuitMoto/admin/partials/dashboard/_newsletter_list.html", {"newsletter_page_obj": newsletter_page_obj})

    return render(request, "circuitMoto/admin/dashboard.html", {
        "stats": stats,
        "prochains": prochains,
        "publies": publies,
        "archives": archives,
        "brouillons": brouillons,
        "inscriptions_recentes_page": inscriptions_recentes_page,
        "documents_attente_page": documents_attente_page,
        "contacts_recents_page": contacts_recents_page,
        "newsletter_page_obj": newsletter_page_obj,
    })
