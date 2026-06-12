# circuitMoto/models.py
from __future__ import annotations
from django.db import models, transaction # type: ignore 
from django.contrib.auth import get_user_model # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from django.core.validators import MinValueValidator, RegexValidator # type: ignore
from django.utils import timezone # type: ignore
from django.utils.text import slugify # type: ignore
from datetime import timedelta
from django.conf import settings
from datetime import date # type: ignore
from modeltranslation.admin import TabbedTranslationAdmin
import uuid
from django.urls import reverse
import os
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils import translation as i18n
from typing import Optional #type: ignore
from decimal import Decimal

Utilisateur = get_user_model()

def initialiser_plan_paiement_solde_unique(inscription: Inscription) -> None:
    """
    Ne garde qu'une seule échéance : le SOLDE = total attendu.
    Supprime ACOMPTE1/ACOMPTE2 s'ils existent.
    """
    total = inscription.total_attendu()
    # Supprimer les acomptes éventuels
    Paiement.objects.filter(
        inscription=inscription,
        libelle__in=[LibellePaiement.ACOMPTE1, LibellePaiement.ACOMPTE2],
    ).delete()

    # Créer / mettre à jour le SOLDE
    Paiement.objects.update_or_create(
        inscription=inscription,
        libelle=LibellePaiement.SOLDE,
        defaults=dict(
            montant_du=total,
            echeance_le=inscription.circuit.date_debut - timedelta(days=7),
        ),
    )

def recalculer_plan_paiement_en_conservant_encaissements(inscription: "Inscription") -> None:
    """
    Recalcule ACOMPTE1 / ACOMPTE2 / SOLDE selon l'inscription actuelle
    sans perdre les encaissements existants.
    """
    circ = inscription.circuit
    total = Decimal(inscription.total_attendu() or 0)

    nb_participants = 1 + (1 if inscription.passager_id else 0)

    a1_unitaire = Decimal(circ.acompte1_par_personne or 0)
    a2_unitaire = Decimal(circ.acompte2_par_personne or 0)

    a1_du = min(Decimal(nb_participants) * a1_unitaire, total)
    reste_apres_a1 = max(Decimal("0"), total - a1_du)

    a2_du = min(Decimal(nb_participants) * a2_unitaire, reste_apres_a1)
    solde_du = max(Decimal("0"), total - a1_du - a2_du)

    today = timezone.now().date()
    e2 = circ.date_debut - timedelta(days=(circ.delai_acompte2_jours or 60))
    es = circ.date_debut - timedelta(days=(circ.delai_solde_jours or 30))

    p1, _ = Paiement.objects.get_or_create(
        inscription=inscription,
        libelle=LibellePaiement.ACOMPTE1,
        defaults={"echeance_le": today, "montant_du": int(a1_du)},
    )
    p2, _ = Paiement.objects.get_or_create(
        inscription=inscription,
        libelle=LibellePaiement.ACOMPTE2,
        defaults={"echeance_le": e2, "montant_du": int(a2_du)},
    )
    ps, _ = Paiement.objects.get_or_create(
        inscription=inscription,
        libelle=LibellePaiement.SOLDE,
        defaults={"echeance_le": es, "montant_du": int(solde_du)},
    )

    p1.montant_du = int(a1_du)
    p1.echeance_le = today
    p1.save(update_fields=["montant_du", "echeance_le", "modifie_le"])

    p2.montant_du = int(a2_du)
    p2.echeance_le = e2
    p2.save(update_fields=["montant_du", "echeance_le", "modifie_le"])

    ps.montant_du = int(solde_du)
    ps.echeance_le = es
    ps.save(update_fields=["montant_du", "echeance_le", "modifie_le"])

# ─────────────────────────────────────────────────────────────
# Utilitaires
# ─────────────────────────────────────────────────────────────

def aujourdhui():
    return timezone.now().date()

def _truncate(s: str, limit: int) -> str:
    return s[:limit] if len(s) > limit else s

def televersement_vers_document(instance: "Document", nom_fichier: str) -> str:
    """
    documents/<code_circuit>/<uuid_inscription>/<type>/<base>-<8>.ext
    -> chaque segment tronqué pour rester très loin des limites.
    """
    code = instance.inscription.circuit.code or f"circuit-{instance.inscription.circuit_id}"
    code_slug = _truncate(slugify(code), 64)  # dossier circuit
    type_slug = _truncate(slugify(instance.type_document.lower()), 32)

    base, ext = os.path.splitext(nom_fichier)
    base_slug = _truncate(slugify(base) or "fichier", 60)
    unique = uuid.uuid4().hex[:8]
    final_name = f"{base_slug}-{unique}{ext.lower()}"

    return os.path.join(
        "documents",
        code_slug,
        str(instance.inscription.id_public),  # 36 chars
        type_slug,
        final_name,
    )

def televersement_vers_decharge_pdf(instance: "DechargeSignee", nom_fichier: str) -> str:
    code = instance.inscription.circuit.code or f"circuit-{instance.inscription.circuit_id}"
    code_slug = _truncate(slugify(code), 64)
    base = f"decharge-{instance.inscription.id_public}.pdf"
    return os.path.join("decharges", code_slug, base)


# ─────────────────────────────────────────────────────────────
# Modèles de base
# ─────────────────────────────────────────────────────────────

class Horodatage(models.Model):
    cree_le = models.DateTimeField(auto_now_add=True, editable=False)
    modifie_le = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        abstract = True


# ─────────────────────────────────────────────────────────────
# Référentiels & Personnes
# ─────────────────────────────────────────────────────────────

class Devise(models.TextChoices):
    XOF = "XOF", "Franc CFA (XOF)"
    EUR = "EUR", "Euro (EUR)"

class GroupeSanguin(models.TextChoices):
    O_POS = "O+", "O+"
    O_NEG = "O-", "O-"
    A_POS = "A+", "A+"
    A_NEG = "A-", "A-"
    B_POS = "B+", "B+"
    B_NEG = "B-", "B-"
    AB_POS = "AB+", "AB+"
    AB_NEG = "AB-", "AB-"

verif_telephone = RegexValidator(
    regex=r"^[0-9+\s\-().]{6,20}$",
    message="Numéro de téléphone invalide.",
)

class Personne(Horodatage):
    prenom = models.CharField("Prénom", max_length=80)
    nom = models.CharField("Nom", max_length=80)
    email = models.EmailField("Email", db_index=True)
    telephone = models.CharField("Téléphone", max_length=32, validators=[verif_telephone], blank=True)
    adresse = models.CharField("Adresse", max_length=255, blank=True)
    code_postal = models.CharField("Code postal", max_length=20, blank=True)
    localite = models.CharField("Localité", max_length=80, blank=True)
    pays = models.CharField("Pays", max_length=80, blank=True)

    nationalite = models.CharField("Nationalité", max_length=80, blank=True)

    date_naissance = models.DateField("Date de naissance", null=True, blank=True)
    numero_carte_identite = models.CharField("N° carte d’identité", max_length=64, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["nom", "prenom"]),
            models.Index(fields=["email"]),
            models.Index(fields=["telephone"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["email", "telephone"], name="uniq_personne_email_tel"),
        ]
        verbose_name = "Personne"
        verbose_name_plural = "Personnes"

    def __str__(self):
        return f"{self.nom.upper()} {self.prenom} — {self.email}"
    

    @property
    def age(self):
        if self.date_naissance:
            today = date.today()
            return today.year - self.date_naissance.year - (
                (today.month, today.day) < (self.date_naissance.month, self.date_naissance.day)
            )
        return None

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}".strip()


class ContactUrgence(Horodatage):
    personne = models.ForeignKey(Personne, on_delete=models.CASCADE, related_name="contacts_urgence")
    nom = models.CharField("Nom", max_length=120)
    lien_parente = models.CharField("Lien de parenté", max_length=80, blank=True)
    telephone = models.CharField("Téléphone", max_length=32, validators=[verif_telephone])

    class Meta:
        verbose_name = "Contact d’urgence"
        verbose_name_plural = "Contacts d’urgence"


class InfosMedicales(Horodatage):
    personne = models.OneToOneField(Personne, on_delete=models.CASCADE, related_name="infos_medicales")
    groupe_sanguin = models.CharField("Groupe sanguin", max_length=4, choices=GroupeSanguin.choices, blank=True)
    hta = models.BooleanField("Hypertension artérielle", default=False)
    asthme = models.BooleanField("Asthme", default=False)
    epilepsie = models.BooleanField("Épilepsie", default=False)
    problemes_peau = models.BooleanField("Eczéma/irritations", default=False)
    vertiges = models.BooleanField("Vertiges", default=False)
    notes = models.TextField("Notes médicales", blank=True)

    class Meta:
        verbose_name = "Infos médicales"
        verbose_name_plural = "Infos médicales"


class Moto(Horodatage):
    proprietaire = models.ForeignKey(Personne, on_delete=models.CASCADE, related_name="motos")
    marque = models.CharField("Marque", max_length=80)
    modele = models.CharField("Modèle", max_length=80, blank=True)
    immatriculation = models.CharField("Immatriculation", max_length=32, blank=True)

    class Meta:
        verbose_name = "Moto"
        verbose_name_plural = "Motos"

    def __str__(self):
        return f"{self.marque} {self.modele} ({self.immatriculation})"


# ─────────────────────────────────────────────────────────────
# Circuits
# ─────────────────────────────────────────────────────────────

class OptionActifManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(actif=True)

class StatutCircuit(models.TextChoices):
    BROUILLON = "BROUILLON", _("Brouillon")
    PUBLIE = "PUBLIE", _("Publié")
    ARCHIVE = "ARCHIVE", _("Archivé")

def circuit_image_upload_to(instance, filename: str) -> str:
    _, ext = os.path.splitext(filename)
    ext = (ext or "").lower()
    uid = uuid.uuid4().hex[:12]
    code = slugify(getattr(instance, "code", "") or getattr(instance, "nom", "") or "circuit")[:60] or "circuit"
    return f"circuitMoto/circuits/{code}/{uid}{ext}"

class Circuit(Horodatage):
    nom = models.CharField(_("Nom du circuit"), max_length=160)
    code = models.SlugField(_("Code"), max_length=80, unique=True, help_text=_("Ex : corse-2025-06"))
    date_debut = models.DateField(_("Date de début"))
    date_fin = models.DateField(_("Date de fin"))
    description = models.TextField(_("Description"), blank=True)
    infos_rdv = models.TextField(_("Infos de rendez-vous"), blank=True)  # Luxembourg/Walin/Marseille…

    image = models.ImageField(
        _("Image (optionnelle)"),
        upload_to=circuit_image_upload_to,
        blank=True,
        null=True,
        help_text=_("JPG/PNG/WebP conseillé. Champ optionnel.")
    )

    capacite = models.PositiveIntegerField(_("Capacité (participants)"), default=0)
    devise = models.CharField(_("Devise"), max_length=3, choices=Devise.choices, default=Devise.XOF)

    # Tarifs de référence
    prix_pilote_unitaire = models.PositiveIntegerField(_("Prix pilote (unitaire)"), validators=[MinValueValidator(0)], default=0)
    prix_passager_unitaire = models.PositiveIntegerField(_("Prix passager (unitaire)"), validators=[MinValueValidator(0)], default=0)

    # ── Echéancier par défaut (montants en UNITE de la devise) ─────────────
    acompte1_par_personne = models.PositiveIntegerField(
        _("Acompte 1 (par personne)"), default=250,
        help_text=_("Montant fixe par personne, dans la devise du circuit.")
    )
    acompte2_par_personne = models.PositiveIntegerField(
        _("Acompte 2 (par personne)"), default=250,
        help_text=_("Montant fixe par personne, dans la devise du circuit.")
    )
    delai_acompte2_jours = models.PositiveIntegerField(
        _("Acompte 2 : J-jours avant départ"), default=60,
        help_text=_("Ex: 60 pour J-60.")
    )
    delai_solde_jours = models.PositiveIntegerField(
        _("Solde : J-jours avant départ"), default=30,
        help_text=_("Ex: 30 pour J-30.")
    )

    # Contenus structurés (pour belle page détail)
    programme = models.TextField(_("Programme (jour par jour)"), blank=True)
    kilometrages = models.TextField(_("Kilométrages indicatifs"), blank=True)
    prix_comprend = models.TextField(_("Le prix comprend"), blank=True)
    prix_ne_comprend_pas = models.TextField(_("Le prix ne comprend pas"), blank=True)
    echeancier_texte = models.TextField(_("Échéancier (texte libre)"), blank=True)

    infos_paiement = models.TextField(
        _("Infos paiement (virement/CGV)"),
        blank=True,
        help_text=_("Texte libre : coordonnées bancaires, référence, CGV, barème annulation, etc.")
    )

    itineraire_active = models.BooleanField(
        _("Afficher la carte interactive"),
        default=False,
        help_text=_("Active le module carte / Street View / jour par jour sur la page détail.")
    )
    itineraire_points = models.JSONField(
        _("Itinéraire cartographique (JSON)"),
        default=list,
        blank=True,
        help_text=_(
            "Liste des jours avec coordonnées. Exemple : "
            "[{\"day\":\"Jour 1\",\"title\":\"Las Vegas\",\"points\":[{\"label\":\"Las Vegas\",\"lat\":36.1699,\"lng\":-115.1398}]}]"
        )
    )
    itineraire_google_maps_url = models.URLField(
        _("Lien Google Maps / My Maps"),
        max_length=700,
        blank=True,
        help_text=_("Lien public optionnel pour ouvrir l'itinéraire complet dans Google Maps.")
    )
    itineraire_embed_url = models.URLField(
        _("URL d'intégration Google Maps"),
        max_length=900,
        blank=True,
        help_text=_("URL iframe optionnelle, utile en secours si la clé Google Maps JS n'est pas configurée.")
    )
    itineraire_street_view_url = models.URLField(
        _("URL d'intégration Street View"),
        max_length=900,
        blank=True,
        help_text=_("URL iframe optionnelle pour afficher une vue immersive en secours.")
    )


    # ✅ Overrides email (facultatifs)
    email_rdv = models.TextField(
        _("Email - RDV / Logistique (override)"),
        blank=True,
        help_text=_("Si vide, le texte par défaut est utilisé. Tu peux mettre du texte multi-lignes.")
    )
    email_organisation = models.TextField(
        _("Email - Organisation du circuit (override)"),
        blank=True,
        help_text=_("Si vide, le texte par défaut est utilisé.")
    )
    email_checklist = models.TextField(
        _("Email - Checklist (override)"),
        blank=True,
        help_text=_("Une ligne = un item. Si vide, la checklist par défaut est utilisée.")
    )

    delai_option_jours = models.PositiveIntegerField(_("Durée de validité d’option (jours)"), default=10)
    statut = models.CharField(_("Statut"), max_length=16, choices=StatutCircuit.choices, default=StatutCircuit.BROUILLON)

    class Meta:
        ordering = ["-date_debut", "code"]
        verbose_name = _("Circuit")
        verbose_name_plural = _("Circuits")

    def __str__(self):
        return f"{self.nom} ({self.code})"

    def clean(self):
            # Ne comparer que si les deux valeurs existent
            if self.date_debut and self.date_fin and self.date_fin < self.date_debut:
                raise ValidationError(_("La date de fin ne peut pas être antérieure à la date de début."))
            
            if (self.delai_acompte2_jours or 0) < 0 or (self.delai_solde_jours or 0) < 0:
                raise ValidationError(_("Les délais d’échéance doivent être des jours positifs (J-N)."))


    def get_absolute_url(self):
        return reverse("circuit_detail", kwargs={"code": self.code})
    
    @property
    def nom_i18n(self):
        lang = (i18n.get_language() or settings.MODELTRANSLATION_DEFAULT_LANGUAGE or "fr").split("-")[0]
        # essaye langue active puis fallbacks
        for code in [lang, *getattr(settings, "MODELTRANSLATION_FALLBACK_LANGUAGES", ("fr",))]:
            v = getattr(self, f"nom_{code}", None)
            if v:
                return v
        return self.nom  # ultime secours

class CategorieOption(models.TextChoices):
    HEBERGEMENT = "HEBERGEMENT", _("Hébergement (chambre single, etc.)")
    CABINE = "CABINE", _("Cabine ferry")
    NUIT_ETAPE = "NUIT_ETAPE", _("Nuit d’étape")
    AUTRE = "AUTRE", _("Autre option")

class OptionCircuit(Horodatage):
    circuit = models.ForeignKey(Circuit, on_delete=models.CASCADE, related_name="options")
    code = models.SlugField(_("Code option"), max_length=64)
    intitule = models.CharField(_("Intitulé"), max_length=160)
    categorie = models.CharField(_("Catégorie"), max_length=16, choices=CategorieOption.choices)
    prix_unitaire = models.PositiveIntegerField(_("Prix unitaire"), validators=[MinValueValidator(0)], default=0)
    facture_par_personne = models.BooleanField(_("Facturé par personne"), default=False)
    quantite_variable = models.BooleanField(_("Quantité variable"), default=False)
    quantite_min = models.PositiveIntegerField(_("Quantité min."), default=0)
    quantite_max = models.PositiveIntegerField(_("Quantité max (0 = illimitée)"), default=0)
    description = models.TextField(_("Description"), blank=True)

    actif = models.BooleanField(_("Actif (disponible à la vente)"), default=True)
    archive_le = models.DateTimeField(_("Archivé le"), null=True, blank=True)

    # ✅ Managers
    objects = models.Manager()        # manager normal (tout, y compris inactifs)
    actifs = OptionActifManager()     # manager filtré (actif=True uniquement)

    class Meta:
        ordering = ("cree_le", "id")
        constraints = [
            # Remplace l’unicité simple par une unicité conditionnelle (PostgreSQL requis) :
            models.UniqueConstraint(
                fields=["circuit", "code"],
                condition=models.Q(actif=True),
                name="uniq_option_code_par_circuit_actives",
            ),
        ]
        verbose_name = _("Option de circuit")
        verbose_name_plural = _("Options de circuit")

    def archiver(self):
        if self.actif:
            self.actif = False
            self.archive_le = timezone.now()
            self.save(update_fields=["actif", "archive_le", "modifie_le"])


# ─────────────────────────────────────────────────────────────
# Inscriptions
# ─────────────────────────────────────────────────────────────

class StatutInscription(models.TextChoices):
    OPTION = "OPTION", "Option posée"
    VALIDE = "VALIDE", "Validée"
    ANNULEE = "ANNULEE", "Annulée"
    TERMINEE = "TERMINEE", "Terminée"

class Inscription(Horodatage):
    """
    Une inscription (1 pilote obligatoire, 0..1 passager).
    Les tarifs unitaires sont « figés » à la création (snapshot) pour garantir la stabilité.
    """
    id_public = models.UUIDField("Identifiant public", default=uuid.uuid4, editable=False, unique=True)
    circuit = models.ForeignKey(Circuit, on_delete=models.PROTECT, related_name="inscriptions")
    pilote = models.ForeignKey(Personne, on_delete=models.PROTECT, related_name="inscriptions_pilote")
    passager = models.ForeignKey(Personne, on_delete=models.PROTECT, null=True, blank=True, related_name="inscriptions_passager")

    # Snapshot devise + tarifs
    devise = models.CharField("Devise", max_length=3, choices=Devise.choices)
    prix_pilote_unitaire = models.PositiveIntegerField("Prix pilote figé", validators=[MinValueValidator(0)], default=0)
    prix_passager_unitaire = models.PositiveIntegerField("Prix passager figé", validators=[MinValueValidator(0)], default=0)

    # Statut & dates
    statut = models.CharField("Statut", max_length=16, choices=StatutInscription.choices, default=StatutInscription.OPTION)
    date_option = models.DateField("Date d’option", default=aujourdhui)
    option_expire_le = models.DateField("Option expire le", null=True, blank=True)
    verrouillee_le = models.DateTimeField("Verrouillée le", null=True, blank=True, help_text="Fige les tarifs/quantités")

    # Totaux figés au verrouillage
    sous_total_fige = models.PositiveIntegerField("Sous-total figé", default=0)
    total_fige = models.PositiveIntegerField("Total figé", default=0)

    notes = models.TextField("Notes", blank=True)

    montant_options_ajoutees = models.PositiveIntegerField(
        "Montant options ajoutées après modification",
        default=0,
    )
    paiement_options_recu = models.PositiveIntegerField(default=0)
    
    cree_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL, related_name="inscriptions_creees")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["circuit", "pilote"], name="uniq_pilote_par_circuit"),
        ]
        indexes = [
            models.Index(fields=["statut"]),
            models.Index(fields=["circuit", "statut"]),
        ]
        verbose_name = "Inscription"
        verbose_name_plural = "Inscriptions"

    def __str__(self):
        duo = f"{self.pilote.nom_complet}" + (f" + {self.passager.nom_complet}" if self.passager_id else "")
        return f"{self.circuit.code} — {duo}"

    # ── Calculs ───────────────────────────────────────────────
    def sous_total_attendu(self) -> int:
        base = (self.prix_pilote_unitaire or 0) + ((self.prix_passager_unitaire or 0) if self.passager_id else 0)
        opts = sum(sel.prix_total() for sel in self.selections_options.all())
        return base + opts

    def total_attendu(self) -> int:
        # Place pour frais/remises si besoin
        return self.sous_total_attendu()

    def est_verrouillee(self) -> bool:
        return bool(self.verrouillee_le)

    @transaction.atomic
    def verrouiller(self):
        """
        Fige les totaux pour édition de facture/reçus.
        Empêche les changements structurants ensuite.
        """
        if self.est_verrouillee():
            return
        self.sous_total_fige = self.sous_total_attendu()
        self.total_fige = self.total_attendu()
        self.verrouillee_le = timezone.now()
        self.save(update_fields=["sous_total_fige", "total_fige", "verrouillee_le", "modifie_le"])

    def clean(self):
        if self.circuit_id and self.option_expire_le and self.option_expire_le < self.date_option:
            raise ValidationError("La date d’expiration d’option ne peut pas précéder la date d’option.")
        if self.est_verrouillee():
            original = type(self).objects.get(pk=self.pk)
            modifies = []
            for champ in ["pilote_id", "passager_id", "prix_pilote_unitaire", "prix_passager_unitaire", "devise"]:
                if getattr(original, champ) != getattr(self, champ):
                    modifies.append(champ)
            if modifies:
                raise ValidationError(f"Inscription verrouillée : modification interdite des champs {modifies}.")

    def save(self, *args, **kwargs):
        nouveau = self._state.adding
        if nouveau:
            # Snapshot initial à partir du circuit
            self.devise = self.devise or self.circuit.devise
            self.prix_pilote_unitaire = self.prix_pilote_unitaire or self.circuit.prix_pilote_unitaire
            self.prix_passager_unitaire = self.prix_passager_unitaire or (self.circuit.prix_passager_unitaire if self.passager_id else 0)
            self.option_expire_le = self.option_expire_le or (self.date_option + timedelta(days=self.circuit.delai_option_jours))
        super().save(*args, **kwargs)


class SelectionOption(Horodatage):
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="selections_options")
    option = models.ForeignKey(OptionCircuit, on_delete=models.PROTECT, related_name="selections")
    quantite = models.PositiveIntegerField("Quantité", default=1, validators=[MinValueValidator(1)])
    prix_unitaire_fige = models.PositiveIntegerField("Prix unitaire figé", validators=[MinValueValidator(0)], default=0)
    pour_passager = models.BooleanField("Pour le passager", default=False, help_text="Si facturé par personne, préciser pilote/passager.")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["inscription", "option", "pour_passager"], name="uniq_option_par_inscription_passager"),
        ]
        verbose_name = "Sélection d’option"
        verbose_name_plural = "Sélections d’options"

    def save(self, *args, **kwargs):
        if self._state.adding and not self.prix_unitaire_fige:
            self.prix_unitaire_fige = self.option.prix_unitaire
        super().save(*args, **kwargs)

    def prix_total(self) -> int:
        return (self.prix_unitaire_fige or 0) * (self.quantite or 0)

    def __str__(self):
        return f"{self.inscription} · {self.option.code} × {self.quantite}"


# ─────────────────────────────────────────────────────────────
# Assurance, Décharge, Documents
# ─────────────────────────────────────────────────────────────

class TypeAssurance(models.TextChoices):
    DEJA_ASSURE = "DEJA_ASSURE", "Déjà assuré"
    DEMANDE_OFFRE = "DEMANDE_OFFRE", "Souhaite une offre"

class Assurance(Horodatage):
    inscription = models.OneToOneField(Inscription, on_delete=models.CASCADE, related_name="assurance")
    type = models.CharField("Type", max_length=16, choices=TypeAssurance.choices, default=TypeAssurance.DEJA_ASSURE)
    compagnie = models.CharField("Compagnie", max_length=120, blank=True)
    numero_police = models.CharField("N° de police", max_length=120, blank=True)

    # ⬇️ NOUVEAU
    telephone_urgence = models.CharField(
        "N° d’urgence (assureur)",
        max_length=32,
        validators=[verif_telephone],
        blank=True,
        default=""   # évite un prompt de default à la migration
    )

    valide_du = models.DateField("Valable du", null=True, blank=True)
    valide_au = models.DateField("Valable au", null=True, blank=True)

    class Meta:
        verbose_name = "Assurance"
        verbose_name_plural = "Assurances"

    def clean(self):
        if self.type == TypeAssurance.DEJA_ASSURE and not self.compagnie:
            raise ValidationError("Indiquez la compagnie d’assurance lorsque « Déjà assuré » est sélectionné.")
        if self.valide_du and self.valide_au and self.valide_au < self.valide_du:
            raise ValidationError("Période d’assurance invalide.")

class DechargeSignee(Horodatage):
    inscription = models.OneToOneField(Inscription, on_delete=models.CASCADE, related_name="decharge")
    version_texte = models.CharField("Version du texte", max_length=64, help_text="Ex : CGV-2025-01")
    nom_signataire = models.CharField("Nom du signataire", max_length=160)
    email_signataire = models.EmailField("Email du signataire")
    signee_le = models.DateTimeField("Signée le", default=timezone.now)
    adresse_ip = models.GenericIPAddressField("Adresse IP", null=True, blank=True)
    # otp_4_derniers = models.CharField("OTP (4 derniers)", max_length=4, blank=True)
    preuve_pdf = models.FileField("Preuve PDF", upload_to=televersement_vers_decharge_pdf, blank=True, max_length=500)

    signature_image = models.ImageField(
        "Signature électronique (PNG)",
        upload_to="signatures/",
        blank=True, null=True, max_length=255
    )


    class Meta:
        verbose_name = "Décharge signée"
        verbose_name_plural = "Décharges signées"

class TypeDocument(models.TextChoices):
    CNI = "CNI", "Carte d’identité"
    PERMIS_CONDUIRE = "PERMIS_CONDUIRE", "Permis de conduire"
    CARTE_GRISE = "CARTE_GRISE", "Carte grise / immatriculation"
    ATTEST_ASSURANCE = "ATTEST_ASSURANCE", "Attestation d’assurance"
    CERTIF_MEDICAL = "CERTIF_MEDICAL", "Certificat médical"
    AUTRE = "AUTRE", "Autre"

class StatutDocument(models.TextChoices):
    EN_ATTENTE = "EN_ATTENTE", "En attente"
    VALIDE = "VALIDE", "Validé"
    REFUSE = "REFUSE", "Refusé"

class Document(Horodatage):
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="documents")
    type_document = models.CharField("Type de document", max_length=32, choices=TypeDocument.choices)
    # fichier = models.FileField("Fichier", upload_to=televersement_vers_document)
    fichier = models.FileField("Fichier", upload_to=televersement_vers_document, max_length=500)
    statut = models.CharField("Statut", max_length=16, choices=StatutDocument.choices, default=StatutDocument.EN_ATTENTE)
    verifie_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL, related_name="documents_verifies")
    verifie_le = models.DateTimeField("Vérifié le", null=True, blank=True)
    note = models.CharField("Note", max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["inscription", "type_document"], name="uniq_type_document_par_inscription"),
        ]
        indexes = [models.Index(fields=["type_document", "statut"])]
        verbose_name = "Document"
        verbose_name_plural = "Documents"

    def __str__(self):
        return f"{self.inscription} · {self.get_type_document_display()}"

    # === AJOUT : méthodes dans la classe ===
    def valider(self, verificateur: Optional[Utilisateur] = None):
        self.statut = StatutDocument.VALIDE
        self.verifie_par = verificateur
        self.verifie_le = timezone.now()
        self.save(update_fields=["statut", "verifie_par", "verifie_le", "modifie_le"])

    def refuser(self, raison: str, verificateur: Optional[Utilisateur] = None):
        self.statut = StatutDocument.REFUSE
        self.note = (raison or "")[:255]
        self.verifie_par = verificateur
        self.verifie_le = timezone.now()
        self.save(update_fields=["statut", "note", "verifie_par", "verifie_le", "modifie_le"])


# ─────────────────────────────────────────────────────────────
# Paiements HORS système (encaissements manuels)
# ─────────────────────────────────────────────────────────────

class StatutPaiement(models.TextChoices):
    A_PAYER = "A_PAYER", "À payer"
    PARTIEL = "PARTIEL", "Partiel"
    PAYE = "PAYE", "Payé"
    ANNULE = "ANNULE", "Annulé"

class LibellePaiement(models.TextChoices):
    ACOMPTE1 = "ACOMPTE1", "Acompte 1"
    ACOMPTE2 = "ACOMPTE2", "Acompte 2"
    SOLDE = "SOLDE", "Solde"
    AUTRE = "AUTRE", "Autre"

class MethodePaiement(models.TextChoices):
    ESPECES = "ESPECES", "Espèces"
    VIREMENT = "VIREMENT", "Virement bancaire"
    CHEQUE = "CHEQUE", "Chèque"
    MOBILE_MONEY = "MOBILE_MONEY", "Mobile Money"

class Paiement(Horodatage):
    """
    Représente une ligne d'échéancier (montant dû + date d’échéance)
    et l'encaissement manuel associé (montant perçu, date, méthode).
    """
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="paiements")
    libelle = models.CharField("Libellé", max_length=16, choices=LibellePaiement.choices, default=LibellePaiement.AUTRE)

    # Attendu
    echeance_le = models.DateField("Échéance", null=True, blank=True)
    montant_du = models.PositiveIntegerField("Montant attendu", validators=[MinValueValidator(0)], default=0)

    # Perçu (manuel)
    montant_encaisse = models.PositiveIntegerField("Montant encaissé", validators=[MinValueValidator(0)], default=0)
    encaisse_le = models.DateField("Payé le", null=True, blank=True)
    methode = models.CharField("Méthode", max_length=16, choices=MethodePaiement.choices, blank=True)
    reference = models.CharField("Référence (bordereau, virement…)", max_length=120, blank=True)

    statut = models.CharField("Statut", max_length=16, choices=StatutPaiement.choices, default=StatutPaiement.A_PAYER)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["inscription", "libelle"], name="uniq_libelle_par_inscription"),
        ]
        indexes = [
            models.Index(fields=["libelle"]),
            models.Index(fields=["statut"]),
        ]
        verbose_name = "Paiement (hors système)"
        verbose_name_plural = "Paiements (hors système)"

    def clean(self):
        if self.montant_encaisse and not self.encaisse_le:
            raise ValidationError("Renseignez la date de paiement (« Payé le »).")
        if self.montant_encaisse > 0 and not self.methode:
            raise ValidationError("Renseignez la méthode de paiement.")
        if self.montant_encaisse > self.montant_du and self.montant_du > 0:
            raise ValidationError("Le montant encaissé dépasse le montant attendu.")

    def recalculer_statut(self):
        if self.montant_encaisse == 0:
            self.statut = StatutPaiement.A_PAYER
        elif 0 < self.montant_encaisse < (self.montant_du or 0):
            self.statut = StatutPaiement.PARTIEL
        else:
            self.statut = StatutPaiement.PAYE

    def save(self, *args, **kwargs):
        self.recalculer_statut()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.inscription} · {self.get_libelle_display()} — {self.get_statut_display()}"


# ─────────────────────────────────────────────────────────────
# Rappels & Audit
# ─────────────────────────────────────────────────────────────

class CanalRappel(models.TextChoices):
    EMAIL = "EMAIL", "Email"
    SMS = "SMS", "SMS"
    WHATSAPP = "WHATSAPP", "WhatsApp"

class TypeRappel(models.TextChoices):
    EXPIRATION_OPTION = "EXPIRATION_OPTION", "Expiration d’option"
    RELANCE_ACOMPTE1 = "RELANCE_ACOMPTE1", "Relance Acompte 1"
    RELANCE_ACOMPTE2 = "RELANCE_ACOMPTE2", "Relance Acompte 2"
    RELANCE_SOLDE = "RELANCE_SOLDE", "Relance Solde"
    DOCUMENT_MANQUANT = "DOCUMENT_MANQUANT", "Document manquant"
    GENERIQUE = "GENERIQUE", "Générique"

class JournalRappel(Horodatage):
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="journaux_rappel")
    type_rappel = models.CharField("Type", max_length=32, choices=TypeRappel.choices)
    canal = models.CharField("Canal", max_length=16, choices=CanalRappel.choices)
    destinataire = models.CharField("Destinataire", max_length=160)
    envoye_le = models.DateTimeField("Envoyé le", default=timezone.now)
    extrait_message = models.CharField("Aperçu du message", max_length=255, blank=True)

    class Meta:
        indexes = [models.Index(fields=["type_rappel", "canal", "envoye_le"])]
        verbose_name = "Journal de rappel"
        verbose_name_plural = "Journaux de rappel"


class JournalAudit(Horodatage):
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="journaux_audit", null=True, blank=True)
    acteur = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL, related_name="actions_audit")
    action = models.CharField("Action", max_length=80)
    donnees = models.JSONField("Données", default=dict, blank=True)

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "Audit"
        verbose_name_plural = "Audit"


# ─────────────────────────────────────────────────────────────
# Aide métier
# ─────────────────────────────────────────────────────────────

def initialiser_plan_paiement_par_defaut(inscription: Inscription) -> None:
    """
    Crée un plan Acompte1 / Acompte2 / Solde à partir du total attendu,
    en s’appuyant sur les paramètres du Circuit.
    - Acompte 1 : "à la validation" (échéance = date du jour)
    - Acompte 2 : J - delai_acompte2_jours
    - Solde     : J - delai_solde_jours
    Les montants d’acomptes sont *par personne*.
    """
    from django.utils import timezone

    circ = inscription.circuit
    total = inscription.total_attendu()

    nb_participants = 1 + (1 if inscription.passager_id else 0)

    a1_unitaire = circ.acompte1_par_personne or 0
    a2_unitaire = circ.acompte2_par_personne or 0

    a1 = min(nb_participants * a1_unitaire, total)
    reste_apres_a1 = max(0, total - a1)

    a2 = min(nb_participants * a2_unitaire, reste_apres_a1)
    reste = max(0, total - a1 - a2)

    # Echéances
    today = timezone.now().date()
    e2 = circ.date_debut - timedelta(days=(circ.delai_acompte2_jours or 60))
    es = circ.date_debut - timedelta(days=(circ.delai_solde_jours or 30))

    Paiement.objects.update_or_create(
        inscription=inscription, libelle=LibellePaiement.ACOMPTE1,
        defaults=dict(montant_du=a1, echeance_le=today),
    )
    Paiement.objects.update_or_create(
        inscription=inscription, libelle=LibellePaiement.ACOMPTE2,
        defaults=dict(montant_du=a2, echeance_le=e2),
    )
    Paiement.objects.update_or_create(
        inscription=inscription, libelle=LibellePaiement.SOLDE,
        defaults=dict(montant_du=reste, echeance_le=es),
    )

class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=100, blank=True, default="footer")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.email
    
# =========================
# BALADES 1 JOUR
# =========================

class BaladeJour(Horodatage):
    CODE_LIEN_CHOICES = [
        ("", "Pas de sous-lien"),
        ("A", "A — Moto Zenith Huy"),
        ("B", "B — Zone Rouge"),
        ("C", "C — Ducati Sambreville"),
        ("D", "D — JL Selection Neufchateau"),
        ("E", "E — Moto Casu Mons"),
        ("F", "F — Harley Liège"),
        ("G", "G — XM Moto"),
    ]

    date_debut = models.DateField("Date de début")
    date_fin = models.DateField("Date de fin", null=True, blank=True)
    date_affichage = models.CharField(
        "Date affichée",
        max_length=80,
        blank=True,
        help_text="Ex: 9 et 10/5. Si vide, on affiche automatiquement la date."
    )

    titre = models.CharField("Titre / circuit", max_length=220)
    guide = models.CharField("Guide", max_length=120, blank=True, default="libre")

    code_lien = models.CharField(
        "Code sous-lien",
        max_length=1,
        choices=CODE_LIEN_CHOICES,
        blank=True,
        default="",
        db_index=True,
    )

    slug_lien = models.SlugField(
        "Slug du sous-lien",
        max_length=180,
        blank=True,
        default="",
        db_index=True,
        help_text="Ex: zone-rouge ou moto-zenith-huy-namur-le-condroz"
    )
    actif = models.BooleanField("Actif", default=True)
    ordre = models.PositiveIntegerField("Ordre d'affichage", default=0)

    class Meta:
        ordering = ["date_debut", "ordre", "titre"]
        indexes = [
            models.Index(fields=["actif", "date_debut"]),
            models.Index(fields=["code_lien", "actif", "date_debut"]),
        ]
        verbose_name = "Balade 1 jour"
        verbose_name_plural = "Balades 1 jour"

    def __str__(self):
        return f"{self.date_humaine()} — {self.titre}"

    def date_humaine(self):
        if self.date_affichage:
            return self.date_affichage.strip()
        if self.date_fin and self.date_fin != self.date_debut:
            return f"{self.date_debut:%d/%m/%Y} → {self.date_fin:%d/%m/%Y}"
        return f"{self.date_debut:%d/%m/%Y}"


class DemandeProgrammeBalade(Horodatage):
    prenom = models.CharField("Prénom", max_length=80)
    nom = models.CharField("Nom", max_length=80)
    email = models.EmailField("Email", db_index=True)
    telephone = models.CharField(
        "Téléphone",
        max_length=32,
        validators=[verif_telephone],
        blank=True
    )

    commentaire = models.TextField("Commentaire", blank=True)

    balades = models.ManyToManyField(
        BaladeJour,
        related_name="demandes_programme",
        verbose_name="Balades sélectionnées"
    )

    traite = models.BooleanField("Traité", default=False, db_index=True)
    source = models.CharField("Source", max_length=120, blank=True, default="page_balades_1_jour")

    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.CharField("User agent", max_length=255, blank=True)

    class Meta:
        ordering = ["-cree_le"]
        indexes = [
            models.Index(fields=["email", "cree_le"]),
            models.Index(fields=["traite", "cree_le"]),
        ]
        verbose_name = "Demande programme balade"
        verbose_name_plural = "Demandes programme balades"

    def __str__(self):
        return f"{self.prenom} {self.nom} — {self.email}"

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}".strip()


# =========================
# PRE PROGRAMME 2027
# =========================

class Programme2027Categorie(models.TextChoices):
    GRAND_VOYAGE = "GRAND_VOYAGE", "Grand voyage"
    EUROPE = "EUROPE", "Europe"
    FRANCE_BELGIQUE = "FRANCE_BELGIQUE", "France / Belgique"
    RAID = "RAID", "Raid / aventure"


class Programme2027Circuit(Horodatage):
    titre = models.CharField("Circuit", max_length=180)
    slug = models.SlugField("Slug", max_length=190, unique=True)
    mois = models.CharField("Mois / periode", max_length=80)
    duree = models.CharField("Duree", max_length=80)
    formule = models.CharField("Formule", max_length=180, blank=True)
    categorie = models.CharField(
        "Categorie",
        max_length=24,
        choices=Programme2027Categorie.choices,
        default=Programme2027Categorie.EUROPE,
        db_index=True,
    )
    lien_reference = models.URLField("Lien reference", max_length=700, blank=True)
    note = models.TextField("Note interne", blank=True)
    ordre = models.PositiveIntegerField("Ordre d'affichage", default=0, db_index=True)
    actif = models.BooleanField("Actif", default=True, db_index=True)

    class Meta:
        ordering = ["ordre", "titre"]
        indexes = [
            models.Index(fields=["actif", "ordre"], name="cm_p27c_act_ord_idx"),
            models.Index(fields=["categorie", "actif"], name="cm_p27c_cat_act_idx"),
        ]
        verbose_name = "Circuit pre programme 2027"
        verbose_name_plural = "Circuits pre programme 2027"

    def __str__(self):
        return f"{self.titre} - {self.mois}"

    @property
    def label_public(self):
        return f"{self.titre} - {self.mois} - {self.duree}"


class NiveauInteret2027(models.TextChoices):
    CURIEUX = "CURIEUX", "Curieux"
    INTERESSE = "INTERESSE", "Interesse"
    TRES_INTERESSE = "TRES_INTERESSE", "Tres interesse"
    PRET_A_RESERVER = "PRET_A_RESERVER", "Pret a reserver"


class DelaiDecision2027(models.TextChoices):
    MAINTENANT = "MAINTENANT", "Des ouverture des reservations"
    TROIS_MOIS = "TROIS_MOIS", "Dans les 3 mois"
    PLUS_TARD = "PLUS_TARD", "Plus tard"
    A_RECONTACTER = "A_RECONTACTER", "A recontacter"


class Programme2027Interest(Horodatage):
    prenom = models.CharField("Prenom", max_length=80)
    nom = models.CharField("Nom", max_length=80)
    email = models.EmailField("Email", db_index=True)
    telephone = models.CharField("Telephone", max_length=32, validators=[verif_telephone], blank=True)
    adresse = models.CharField("Adresse", max_length=255, blank=True)
    code_postal = models.CharField("Code postal", max_length=20, blank=True)
    localite = models.CharField("Localite", max_length=80, blank=True)
    pays = models.CharField("Pays", max_length=80, blank=True)

    profil = models.CharField("Profil voyageur", max_length=120, blank=True)
    vehicule = models.CharField("Vehicule / preference", max_length=160, blank=True)
    participants_previsionnels = models.PositiveSmallIntegerField("Nombre de participants prevus", default=1)
    delai_decision = models.CharField(
        "Delai de decision",
        max_length=20,
        choices=DelaiDecision2027.choices,
        default=DelaiDecision2027.A_RECONTACTER,
    )
    commentaire = models.TextField("Commentaire", blank=True)

    circuits = models.ManyToManyField(
        Programme2027Circuit,
        through="Programme2027Selection",
        related_name="interesses",
        verbose_name="Circuits interesses",
    )

    consent = models.BooleanField("Accepte d'etre contacte", default=False)
    newsletter_optin = models.BooleanField("Souhaite recevoir les informations Pulsion Horizon", default=False)
    traite = models.BooleanField("Traite", default=False, db_index=True)
    source = models.CharField("Source", max_length=120, blank=True, default="pre_programme_2027")
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.CharField("User agent", max_length=255, blank=True)

    class Meta:
        ordering = ["-cree_le"]
        indexes = [
            models.Index(fields=["email", "cree_le"], name="cm_p27i_email_idx"),
            models.Index(fields=["traite", "cree_le"], name="cm_p27i_traite_idx"),
            models.Index(fields=["delai_decision", "cree_le"], name="cm_p27i_decision_idx"),
        ]
        verbose_name = "Interesse pre programme 2027"
        verbose_name_plural = "Interesses pre programme 2027"

    def __str__(self):
        return f"{self.prenom} {self.nom} - {self.email}"

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}".strip()


class Programme2027Selection(Horodatage):
    demande = models.ForeignKey(
        Programme2027Interest,
        on_delete=models.CASCADE,
        related_name="selections",
    )
    circuit = models.ForeignKey(
        Programme2027Circuit,
        on_delete=models.CASCADE,
        related_name="selections",
    )
    niveau_interet = models.CharField(
        "Niveau d'interet",
        max_length=20,
        choices=NiveauInteret2027.choices,
        default=NiveauInteret2027.INTERESSE,
        db_index=True,
    )
    participants = models.PositiveSmallIntegerField("Participants pour ce circuit", default=1)
    mode_prefere = models.CharField("Mode prefere", max_length=140, blank=True)
    commentaire = models.CharField("Precision", max_length=500, blank=True)

    class Meta:
        ordering = ["circuit__ordre", "circuit__titre"]
        constraints = [
            models.UniqueConstraint(fields=["demande", "circuit"], name="uniq_programme2027_selection"),
        ]
        indexes = [
            models.Index(fields=["circuit", "niveau_interet"], name="cm_p27s_circuit_idx"),
            models.Index(fields=["demande", "niveau_interet"], name="cm_p27s_demande_idx"),
        ]
        verbose_name = "Selection pre programme 2027"
        verbose_name_plural = "Selections pre programme 2027"

    def __str__(self):
        return f"{self.demande} - {self.circuit} ({self.niveau_interet})"


class AccountFlags(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="flags")
    must_change_password = models.BooleanField(default=False)
    # On mémorise le hash du mot de passe provisoire pour interdire sa réutilisation
    initial_password_hash = models.CharField(max_length=256, blank=True, default="")

    def __str__(self):
        return f"Flags<{self.user_id}> must_change={self.must_change_password}"

class SitePrefs(models.Model):
    """Préférences globales du site (singleton id=1)."""
    id = models.SmallAutoField(primary_key=True)  # on forcera id=1
    emails_pause_all = models.BooleanField(default=False)
    emails_pause_pilote = models.BooleanField(default=False)
    emails_pause_passager = models.BooleanField(default=False)
    modifie_le = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.id = 1  # singleton
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        # Sync avec settings à chaque appel (si tu veux)
        obj.emails_pause_all = getattr(settings, "EMAILS_PAUSE_TOUS_UTILISATEURS", False)
        obj.emails_pause_pilote = getattr(settings, "EMAILS_PAUSE_PILOTE", False)
        obj.emails_pause_passager = getattr(settings, "EMAILS_PAUSE_PASSAGER", False)
        obj.save(update_fields=["emails_pause_all", "emails_pause_pilote", "emails_pause_passager", "modifie_le"])
        return obj

    @classmethod
    def as_flags(cls):
        try:
            p = cls.get()
            return {
                "all": p.emails_pause_all,
                "pilote": p.emails_pause_pilote,
                "passager": p.emails_pause_passager,
            }
        except Exception:
            # fallback settings.py si la table n’existe pas encore
            return {
                "all": getattr(settings, "EMAILS_PAUSE_TOUS_UTILISATEURS", False),
                "pilote": getattr(settings, "EMAILS_PAUSE_PILOTE", False),
                "passager": getattr(settings, "EMAILS_PAUSE_PASSAGER", False),
            }
        
class PasswordHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="password_histories")
    encoded = models.CharField(max_length=256)  # hash Django (pbkdf2, argon2…)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PasswordHistory(user={self.user_id}, at={self.created_at:%Y-%m-%d %H:%M})"
    
# ----- CONTACT -----

class TypeDemande(models.TextChoices):
    INFO = "INFO", _("Demande d’information")
    RECLAMATION = "RECLAMATION", _("Réclamation")
    DEVIS = "DEVIS", _("Demande de devis")
    AUTRE = "AUTRE", _("Autre")

class ContactMessage(Horodatage):
    # Infos perso
    prenom = models.CharField(_("Prénom"), max_length=80)
    nom = models.CharField(_("Nom"), max_length=80)
    email = models.EmailField(_("Email"))
    telephone = models.CharField(_("Téléphone"), max_length=32, validators=[verif_telephone], blank=True)
    adresse = models.CharField(_("Adresse"), max_length=255, blank=True)

    # Intérêt pour un circuit
    interesse_circuit = models.BooleanField(_("Intéressé par un circuit ?"), default=False)
    statut_circuit = models.CharField(_("Statut du circuit"), max_length=16, choices=StatutCircuit.choices, blank=True)
    circuit = models.ForeignKey(Circuit, on_delete=models.SET_NULL, null=True, blank=True, related_name="contacts")

    # Contenu
    type_demande = models.CharField(_("Type de demande"), max_length=16, choices=TypeDemande.choices, default=TypeDemande.INFO)
    message = models.TextField(_("Votre message"))

    # Consentement & suivi
    consent = models.BooleanField(_("J’accepte d’être contacté"), default=False)
    traite = models.BooleanField(_("Traité"), default=False)
    ip = models.GenericIPAddressField(_("Adresse IP"), null=True, blank=True)
    user_agent = models.CharField(_("User-Agent"), max_length=255, blank=True)

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = _("Message de contact")
        verbose_name_plural = _("Messages de contact")
        indexes = [
            models.Index(fields=["cree_le"]),
            models.Index(fields=["statut_circuit"]),
            models.Index(fields=["traite"]),
        ]

    def __str__(self):
        cible = f" · {self.circuit.code}" if self.circuit_id else ""
        return f"{self.nom.upper()} {self.prenom} — {self.type_demande}{cible}"

class SiteVisitor(models.Model):
    ip = models.GenericIPAddressField("Adresse IP", null=True, blank=True)
    session_key = models.CharField("Clé de session", max_length=64, blank=True, db_index=True)
    path = models.CharField("Page visitée", max_length=255, blank=True, default="/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Visiteur du site"
        verbose_name_plural = "Visiteurs du site"
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["ip"]),
            models.Index(fields=["session_key"]),
        ]

    def __str__(self):
        return f"{self.ip or 'IP inconnue'} - {self.created_at:%Y-%m-%d %H:%M}"
