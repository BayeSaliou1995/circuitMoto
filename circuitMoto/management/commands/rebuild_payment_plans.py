# circuitMoto/management/commands/rebuild_payment_plans.py
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from circuitMoto.models import (
    Inscription,
    LibellePaiement,
    StatutPaiement,
    recalculer_plan_paiement_en_conservant_encaissements,
)


class Command(BaseCommand):
    help = "Recalcule les échéanciers ACOMPTE1/ACOMPTE2/SOLDE des inscriptions existantes et redistribue les anciens paiements SOLDE."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-solde",
            action="store_true",
            help="Ne traite que les inscriptions qui n'ont actuellement qu'une ligne SOLDE.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche ce qui serait fait sans enregistrer les changements.",
        )

    def handle(self, *args, **options):
        qs = Inscription.objects.select_related("circuit", "pilote", "passager").prefetch_related("paiements")

        if options["only_solde"]:
            filtered = []
            for ins in qs:
                libelles = sorted([p.libelle for p in ins.paiements.all()])
                if libelles == ["SOLDE"] or libelles == []:
                    filtered.append(ins.pk)
            qs = qs.filter(pk__in=filtered)

        total = qs.count()
        done = 0

        self.stdout.write(self.style.NOTICE(f"{total} inscription(s) à traiter."))

        for ins in qs.iterator():
            before = list(ins.paiements.all().values_list("libelle", "montant_du", "montant_encaisse"))

            # ancien encaissé total avant restructuration
            old_solde = ins.paiements.filter(libelle=LibellePaiement.SOLDE).first()
            old_solde_encaisse = Decimal(old_solde.montant_encaisse or 0) if old_solde else Decimal("0")

            if options["dry_run"]:
                self.stdout.write(
                    f"[DRY RUN] {ins.id_public} | avant={before} | ancien_solde_encaisse={old_solde_encaisse}"
                )
                continue

            with transaction.atomic():
                # 1) recrée / recalcule proprement ACOMPTE1 / ACOMPTE2 / SOLDE
                recalculer_plan_paiement_en_conservant_encaissements(ins)
                ins.refresh_from_db()

                # 2) si ancien paiement uniquement sur SOLDE, on le redistribue intelligemment
                if old_solde_encaisse > 0:
                    p1 = ins.paiements.filter(libelle=LibellePaiement.ACOMPTE1).first()
                    p2 = ins.paiements.filter(libelle=LibellePaiement.ACOMPTE2).first()
                    ps = ins.paiements.filter(libelle=LibellePaiement.SOLDE).first()

                    remaining = old_solde_encaisse

                    def apply_amount(pmt, amount_to_apply):
                        if not pmt or amount_to_apply <= 0:
                            return amount_to_apply

                        du = Decimal(pmt.montant_du or 0)
                        a_imputer = min(amount_to_apply, du)
                        pmt.montant_encaisse = int(a_imputer)

                        if a_imputer == 0:
                            pmt.statut = StatutPaiement.A_PAYER
                        elif a_imputer < du:
                            pmt.statut = StatutPaiement.PARTIEL
                        else:
                            pmt.statut = StatutPaiement.PAYE

                        pmt.save(update_fields=["montant_encaisse", "statut", "modifie_le"])
                        return amount_to_apply - a_imputer

                    remaining = apply_amount(p1, remaining)
                    remaining = apply_amount(p2, remaining)
                    remaining = apply_amount(ps, remaining)

                    # si par sécurité il reste encore quelque chose, on l'ajoute au solde
                    if ps and remaining > 0:
                        current = Decimal(ps.montant_encaisse or 0)
                        ps.montant_encaisse = int(current + remaining)

                        du = Decimal(ps.montant_du or 0)
                        if Decimal(ps.montant_encaisse) == 0:
                            ps.statut = StatutPaiement.A_PAYER
                        elif Decimal(ps.montant_encaisse) < du:
                            ps.statut = StatutPaiement.PARTIEL
                        else:
                            ps.statut = StatutPaiement.PAYE

                        ps.save(update_fields=["montant_encaisse", "statut", "modifie_le"])

            ins.refresh_from_db()
            after = list(ins.paiements.all().values_list("libelle", "montant_du", "montant_encaisse"))

            self.stdout.write(
                self.style.SUCCESS(f"{ins.id_public} | avant={before} | après={after}")
            )
            done += 1

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Simulation terminée. Aucun changement enregistré."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Terminé : {done} inscription(s) mises à jour."))