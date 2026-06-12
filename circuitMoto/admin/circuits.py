# -*- coding: utf-8 -*-
"""Vues back-office liées aux circuits."""
from __future__ import annotations

import datetime as dt

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator  # type: ignore
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..models import Circuit, Inscription, OptionCircuit
from .forms import CircuitForm, OptionFormSet


@staff_member_required
def circuit_list(request):
    q = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "-date")
    sort_map = {
        "-date": "-date_debut",
        "date": "date_debut",
        "nom": "nom",
        "-cap": "-capacite",
        "cap": "capacite",
    }
    order_by = sort_map.get(sort, "-date_debut")

    qs = Circuit.objects.all().annotate(nb=Count("inscriptions")).order_by(order_by)
    if q:
        qs = qs.filter(Q(nom__icontains=q) | Q(code__icontains=q) | Q(description__icontains=q))

    try:
        per = int(request.GET.get("per", 20))
        per_page = max(5, min(per, 100))
    except (TypeError, ValueError):
        per_page = 20

    paginator = Paginator(qs, per_page)
    page = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "circuitMoto/admin/circuits_list.html", {
        "circuits": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "q": q,
        "sort": sort,
        "per": per_page,
        "querystring": params.urlencode(),
    })


@staff_member_required
@transaction.atomic
def circuit_create(request):
    if request.method == "POST":
        form = CircuitForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_image = form.cleaned_data.get("image")
            circuit = form.save(commit=False)
            if uploaded_image:
                circuit.image = None
            circuit.save()
            formset = OptionFormSet(request.POST, instance=circuit, prefix="opts")
            if formset.is_valid():
                formset.save()
                if uploaded_image:
                    circuit.image = uploaded_image
                    circuit.save()
                messages.success(request, "Circuit créé avec ses options.")
                return redirect("bo_circuit_list")
            circuit.delete()
        else:
            formset = OptionFormSet(request.POST, prefix="opts")
    else:
        form = CircuitForm()
        formset = OptionFormSet(prefix="opts")
    return render(request, "circuitMoto/admin/circuits_form.html", {"form": form, "formset": formset, "mode": "create"})


@staff_member_required
def circuit_detail(request, pk: int):
    qs = (
        Circuit.objects
        .prefetch_related(
            Prefetch("options", queryset=OptionCircuit.objects.order_by("categorie", "intitule")),
            Prefetch("inscriptions", queryset=Inscription.objects.select_related("pilote", "passager").order_by("-cree_le")),
        )
        .annotate(nb_inscriptions=Count("inscriptions"))
    )
    circuit = get_object_or_404(qs, pk=pk)
    capacite = circuit.capacite or 0
    pct = int(round((circuit.nb_inscriptions / capacite) * 100)) if capacite else 0
    return render(request, "circuitMoto/admin/circuits_detail.html", {"c": circuit, "pct": pct})


@staff_member_required
@transaction.atomic
def circuit_edit(request, pk):
    obj = get_object_or_404(Circuit, pk=pk)
    if request.method == "POST":
        form = CircuitForm(request.POST, request.FILES, instance=obj)
        formset = OptionFormSet(request.POST, instance=obj, prefix="opts")
        if form.is_valid() and formset.is_valid():
            form.save()
            try:
                formset.save()
            except ProtectedError:
                to_archive_ids = []
                for f in formset.forms:
                    if f.cleaned_data.get("DELETE") and f.instance.pk:
                        to_archive_ids.append(f.instance.pk)
                if to_archive_ids:
                    OptionCircuit.objects.filter(pk__in=to_archive_ids, circuit=obj).update(actif=False, archive_le=timezone.now())
                    messages.warning(request, "Certaines options déjà utilisées ont été archivées au lieu d’être supprimées.")
            messages.success(request, "Circuit mis à jour.")
            return redirect("bo_circuit_list")
    else:
        form = CircuitForm(instance=obj)
        formset = OptionFormSet(instance=obj, prefix="opts")
    return render(request, "circuitMoto/admin/circuits_form.html", {"form": form, "formset": formset, "mode": "edit", "obj": obj})
