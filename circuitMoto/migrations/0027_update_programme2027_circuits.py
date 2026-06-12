from importlib import import_module

from django.db import migrations


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


def sync_programme_2027(apps, schema_editor):
    Circuit = apps.get_model("circuitMoto", "Programme2027Circuit")
    source = import_module("circuitMoto.migrations.0026_programme2027")
    circuits = source.PROGRAMME_2027_CIRCUITS
    desired_slugs = {item["slug"] for item in circuits}

    for old_slug, new_slug in LEGACY_SLUGS.items():
        old = Circuit.objects.filter(slug=old_slug).first()
        target_exists = Circuit.objects.filter(slug=new_slug).exclude(pk=getattr(old, "pk", None)).exists()
        if old and not target_exists:
            old.slug = new_slug
            old.save(update_fields=["slug"])

    for item in circuits:
        defaults = item.copy()
        slug = defaults.pop("slug")
        defaults["actif"] = True
        Circuit.objects.update_or_create(slug=slug, defaults=defaults)

    Circuit.objects.exclude(slug__in=desired_slugs).update(actif=False)


class Migration(migrations.Migration):

    dependencies = [
        ("circuitMoto", "0026_programme2027"),
    ]

    operations = [
        migrations.RunPython(sync_programme_2027, migrations.RunPython.noop),
    ]
