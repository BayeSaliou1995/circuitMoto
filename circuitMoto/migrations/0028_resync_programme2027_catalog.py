from django.db import migrations


def resync_programme_2027(apps, schema_editor):
    Circuit = apps.get_model("circuitMoto", "Programme2027Circuit")
    from circuitMoto.programme_2027_sync import sync_programme_2027_circuits

    sync_programme_2027_circuits(Circuit)


class Migration(migrations.Migration):

    dependencies = [
        ("circuitMoto", "0017_programme2027circuit_programme2027interest_and_more"),
    ]

    operations = [
        migrations.RunPython(resync_programme_2027, migrations.RunPython.noop),
    ]
