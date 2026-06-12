from __future__ import annotations

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

PROGRAMME_2027_CIRCUITS = [
    {"titre": "Laos", "slug": "laos-fevrier-2027", "mois": "Fevrier", "duree": "14 jours", "formule": "Moto ou 4x4", "categorie": "GRAND_VOYAGE", "ordre": 10},
    {"titre": "Vietnam", "slug": "vietnam-fevrier-2027", "mois": "Fevrier", "duree": "14 jours", "formule": "Moto ou 4x4", "categorie": "GRAND_VOYAGE", "ordre": 20},
    {"titre": "Sud Maroc - moto loc", "slug": "sud-maroc-moto-loc-mars-2027", "mois": "Mars", "duree": "10 jours", "formule": "Moto de location", "categorie": "RAID", "ordre": 30},
    {"titre": "Senegal", "slug": "senegal-mars-2027", "mois": "Mars", "duree": "8 ou 12 jours", "formule": "Moto ou 4x4", "categorie": "GRAND_VOYAGE", "ordre": 40},
    {"titre": "USA", "slug": "usa-avril-2027", "mois": "Avril", "duree": "12 ou 17 jours", "formule": "Harley ou Mustang", "categorie": "GRAND_VOYAGE", "ordre": 50},
    {"titre": "Foret Noire", "slug": "foret-noire-mai-2027", "mois": "Mai", "duree": "4 ou 5 jours", "formule": "Moto", "categorie": "EUROPE", "ordre": 60},
    {"titre": "Sardaigne", "slug": "sardaigne-mai-2027", "mois": "Mai", "duree": "11 ou 13 jours", "formule": "Moto", "categorie": "EUROPE", "ordre": 70},
    {"titre": "Morvan", "slug": "morvan-mai-2027", "mois": "Mai", "duree": "5 ou 6 jours", "formule": "Moto", "categorie": "FRANCE_BELGIQUE", "ordre": 80},
    {"titre": "Corse I", "slug": "corse-i-mai-2027", "mois": "Mai", "duree": "11 ou 13 jours", "formule": "Moto", "categorie": "EUROPE", "ordre": 90},
    {"titre": "Pyrenees", "slug": "pyrenees-mai-2027", "mois": "Mai", "duree": "9 ou 11 jours", "formule": "Moto", "categorie": "FRANCE_BELGIQUE", "ordre": 100},
    {"titre": "Toscane", "slug": "toscane-juin-2027", "mois": "Juin", "duree": "7 ou 9 jours", "formule": "Moto", "categorie": "EUROPE", "ordre": 110},
    {"titre": "Vosges", "slug": "vosges-juin-2027", "mois": "Juin", "duree": "3 ou 4 jours", "formule": "Moto", "categorie": "FRANCE_BELGIQUE", "ordre": 120},
    {"titre": "Corse II", "slug": "corse-ii-juin-2027", "mois": "Juin", "duree": "11 ou 13 jours", "formule": "Moto", "categorie": "EUROPE", "ordre": 130},
    {"titre": "Dolomites I", "slug": "dolomites-i-juin-2027", "mois": "Juin", "duree": "8 ou 9 jours", "formule": "Moto", "categorie": "EUROPE", "ordre": 140},
    {"titre": "Alsace I", "slug": "alsace-i-juin-2027", "mois": "Juin", "duree": "3 ou 5 jours", "formule": "Moto", "categorie": "FRANCE_BELGIQUE", "lien_reference": "https://pulsionhorizon.com/alsace", "ordre": 150},
    {"titre": "Corse autrement", "slug": "corse-autrement-juin-2027", "mois": "Juin", "duree": "11 ou 13 jours", "formule": "Moto", "categorie": "EUROPE", "ordre": 160},
    {"titre": "Cote d'Opale - Normandie", "slug": "cote-opale-normandie-juin-2027", "mois": "Juin", "duree": "4 jours", "formule": "Moto", "categorie": "FRANCE_BELGIQUE", "ordre": 170},
    {"titre": "Normandie - Bretagne", "slug": "normandie-bretagne-juin-2027", "mois": "Juin", "duree": "6 ou 7 jours", "formule": "Moto", "categorie": "FRANCE_BELGIQUE", "ordre": 180},
    {"titre": "Cote d'Opale - Normandie - Bretagne", "slug": "cote-opale-normandie-bretagne-juin-2027", "mois": "Juin", "duree": "8 ou 9 jours", "formule": "Moto", "categorie": "FRANCE_BELGIQUE", "ordre": 190},
    {"titre": "Ecosse", "slug": "ecosse-juin-2027", "mois": "Juin", "duree": "9 jours", "formule": "Moto", "categorie": "EUROPE", "ordre": 200},
    {"titre": "Jura", "slug": "jura-juin-2027", "mois": "Juin", "duree": "5 ou 6 jours", "formule": "Moto", "categorie": "FRANCE_BELGIQUE", "ordre": 210},
    {"titre": "Corse III", "slug": "corse-iii-septembre-2027", "mois": "Septembre", "duree": "11 ou 13 jours", "formule": "Moto", "categorie": "EUROPE", "ordre": 220},
    {"titre": "Corse IV", "slug": "corse-iv-septembre-2027", "mois": "Septembre", "duree": "11 ou 13 jours", "formule": "Moto", "categorie": "EUROPE", "ordre": 230},
    {"titre": "Alpes du sud", "slug": "alpes-du-sud-septembre-2027", "mois": "Septembre", "duree": "9 ou 10 jours", "formule": "Moto", "categorie": "FRANCE_BELGIQUE", "ordre": 240},
    {"titre": "Croatie", "slug": "croatie-septembre-2027", "mois": "Septembre", "duree": "14 ou 15 jours", "formule": "Moto", "categorie": "EUROPE", "ordre": 250},
    {"titre": "Albanie Grece", "slug": "albanie-grece-septembre-2027", "mois": "Septembre", "duree": "14 ou 15 jours", "formule": "Moto", "categorie": "EUROPE", "ordre": 260},
    {"titre": "Champagne", "slug": "champagne-septembre-2027", "mois": "Septembre", "duree": "3 ou 4 jours", "formule": "Moto", "categorie": "FRANCE_BELGIQUE", "ordre": 270},
    {"titre": "Dolomites II", "slug": "dolomites-ii-septembre-2027", "mois": "Septembre", "duree": "8 ou 9 jours", "formule": "Moto", "categorie": "EUROPE", "ordre": 280},
    {"titre": "Alsace II", "slug": "alsace-ii-septembre-2027", "mois": "Septembre", "duree": "3 ou 5 jours", "formule": "Moto", "categorie": "FRANCE_BELGIQUE", "lien_reference": "https://pulsionhorizon.com/alsace", "ordre": 290},
    {"titre": "Usine Guzzi", "slug": "usine-guzzi-septembre-2027", "mois": "Septembre", "duree": "5 jours", "formule": "Moto", "categorie": "EUROPE", "ordre": 300},
    {"titre": "Namibie", "slug": "namibie-octobre-2027", "mois": "Octobre", "duree": "14 jours", "formule": "Moto ou 4x4", "categorie": "GRAND_VOYAGE", "ordre": 310},
    {"titre": "Raid Bxl/Dakar", "slug": "raid-bxl-dakar-octobre-2027", "mois": "Octobre", "duree": "24 jours", "formule": "100% route ou mixte route et piste", "categorie": "RAID", "ordre": 320},
    {"titre": "Raid sud Maroc", "slug": "raid-sud-maroc-octobre-2027", "mois": "Octobre", "duree": "16 jours", "formule": "Route ou piste", "categorie": "RAID", "lien_reference": "https://pulsionhorizon.com/raid-sud-maroc-2026", "ordre": 330},
    {"titre": "Sud Maroc - moto loc", "slug": "sud-maroc-moto-loc-octobre-2027", "mois": "Octobre", "duree": "10 jours", "formule": "Moto de location", "categorie": "RAID", "ordre": 340},
    {"titre": "Senegal", "slug": "senegal-novembre-2027", "mois": "Novembre", "duree": "8 ou 12 jours", "formule": "Moto ou 4x4", "categorie": "GRAND_VOYAGE", "ordre": 350},
]


def programme_2027_circuits() -> list[dict[str, Any]]:
    return [item.copy() for item in PROGRAMME_2027_CIRCUITS]


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
