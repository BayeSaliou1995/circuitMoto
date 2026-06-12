from __future__ import annotations

from importlib import import_module
from typing import Any

from django.db import transaction


LEGACY_SLUGS = {
    "sud-maroc-mars-2027": "sud-maroc-moto-loc-mars-2027",
    "usa-harley-avril-2027": "usa-avril-2027",
    "corse-juin-2027": "corse-ii-juin-2027",
    "corse-septembre-2027": "corse-iii-septembre-2027",
    "dolomites-juin-2027": "dolomites-i-juin-2027",
    "dolomites-septembre-2027": "dolomites-ii-septembre-2027",
    "visite-guzzi-septembre-2027": "usine-guzzi-septembre-2027",
    "alsace-juin-2027": "alsace-i-juin-2027",
    "alsace-septembre-2027": "alsace-ii-septembre-2027",
    "pyrenees-juin-2027": "pyrenees-mai-2027",
    "lorraine-vosges-juin-2027": "vosges-juin-2027",
    "toscane-cinque-terre-lac-de-garde-juin-2027": "toscane-juin-2027",
    "normandie-juin-2027": "cote-opale-normandie-juin-2027",
    "albanie-septembre-2027": "albanie-grece-septembre-2027",
    "raid-maroc-octobre-2027": "raid-sud-maroc-octobre-2027",
    "bxl-dakar-octobre-2027": "raid-bxl-dakar-octobre-2027",
}

SYNC_FIELDS = (
    "titre",
    "mois",
    "duree",
    "formule",
    "categorie",
    "lien_reference",
    "note",
    "ordre",
    "actif",
)


def programme_2027_circuits() -> list[dict[str, Any]]:
    source = import_module("circuitMoto.migrations.0026_programme2027")
    return [item.copy() for item in source.PROGRAMME_2027_CIRCUITS]


def _defaults(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "titre": item["titre"],
        "mois": item["mois"],
        "duree": item["duree"],
        "formule": item.get("formule", ""),
        "categorie": item.get("categorie", "EUROPE"),
        "lien_reference": item.get("lien_reference", ""),
        "note": item.get("note", ""),
        "ordre": item["ordre"],
        "actif": True,
    }


def _has_changes(instance, defaults: dict[str, Any]) -> bool:
    return any(getattr(instance, field) != value for field, value in defaults.items())


def sync_programme_2027_circuits(Circuit, *, deactivate_missing: bool = True, dry_run: bool = False) -> dict[str, Any]:
    circuits = programme_2027_circuits()
    desired_slugs = {item["slug"] for item in circuits}
    report: dict[str, Any] = {
        "created": [],
        "updated": [],
        "unchanged": [],
        "renamed": [],
        "deactivated": [],
        "active_total": 0,
        "desired_total": len(circuits),
    }

    with transaction.atomic():
        for old_slug, new_slug in LEGACY_SLUGS.items():
            old = Circuit.objects.filter(slug=old_slug).first()
            if not old:
                continue

            target_exists = Circuit.objects.filter(slug=new_slug).exclude(pk=old.pk).exists()
            if target_exists:
                continue

            old.slug = new_slug
            old.save(update_fields=["slug", "modifie_le"])
            report["renamed"].append(f"{old_slug} -> {new_slug}")

        for item in circuits:
            slug = item["slug"]
            defaults = _defaults(item)
            instance = Circuit.objects.filter(slug=slug).first()

            if instance is None:
                Circuit.objects.create(slug=slug, **defaults)
                report["created"].append(slug)
                continue

            if _has_changes(instance, defaults):
                for field, value in defaults.items():
                    setattr(instance, field, value)
                instance.save(update_fields=[*SYNC_FIELDS, "modifie_le"])
                report["updated"].append(slug)
            else:
                report["unchanged"].append(slug)

        if deactivate_missing:
            stale_qs = Circuit.objects.exclude(slug__in=desired_slugs).filter(actif=True)
            report["deactivated"] = list(stale_qs.values_list("slug", flat=True))
            stale_qs.update(actif=False)

        report["active_total"] = Circuit.objects.filter(actif=True).count()

        if dry_run:
            transaction.set_rollback(True)

    return report
