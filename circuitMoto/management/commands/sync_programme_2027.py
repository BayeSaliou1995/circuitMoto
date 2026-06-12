from django.core.management.base import BaseCommand

from circuitMoto.models import Programme2027Circuit
from circuitMoto.programme_2027_sync import programme_2027_circuits, sync_programme_2027_circuits


class Command(BaseCommand):
    help = "Synchronise les circuits du pre programme 2027 avec le catalogue officiel."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simule la synchronisation sans enregistrer les changements.",
        )
        parser.add_argument(
            "--keep-extra",
            action="store_true",
            help="Ne desactive pas les anciens circuits absents du catalogue officiel.",
        )
        parser.add_argument(
            "--show-order",
            action="store_true",
            help="Affiche l'ordre officiel apres la synchronisation.",
        )

    def handle(self, *args, **options):
        report = sync_programme_2027_circuits(
            Programme2027Circuit,
            deactivate_missing=not options["keep_extra"],
            dry_run=options["dry_run"],
        )

        prefix = "[DRY RUN] " if options["dry_run"] else ""
        self.stdout.write(self.style.NOTICE(f"{prefix}{report['desired_total']} circuit(s) dans le catalogue officiel."))

        for key, label in (
            ("renamed", "Slugs renommes"),
            ("created", "Circuits crees"),
            ("updated", "Circuits mis a jour"),
            ("deactivated", "Anciens circuits desactives"),
            ("unchanged", "Circuits deja OK"),
        ):
            values = report[key]
            style = self.style.SUCCESS if key in {"created", "updated", "renamed"} else self.style.NOTICE
            self.stdout.write(style(f"{prefix}{label}: {len(values)}"))
            if values and key != "unchanged":
                for value in values:
                    self.stdout.write(f"  - {value}")

        if options["show_order"]:
            self.stdout.write("")
            self.stdout.write(self.style.NOTICE("Ordre officiel 2027:"))
            for item in programme_2027_circuits():
                self.stdout.write(
                    f"{item['ordre']:03d} | {item['mois']} | {item['titre']} | {item['duree']}"
                )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Simulation terminee. Aucun changement enregistre."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Synchronisation terminee. Circuits actifs: {report['active_total']}."))
