# circuitMoto/forms.py
from typing import Optional, Dict, Any
from django import forms #type: ignore
from django.core.validators import MinValueValidator, RegexValidator #type: ignore
from django.utils.translation import gettext_lazy as _ #type: ignore
import datetime as _dt
from django.utils import timezone
from django.db.models import Q
from django.utils.text import format_lazy
from django.utils.formats import localize

from .models import (
    Circuit, Personne, Moto, Assurance, TypeAssurance,
    TypeDocument, StatutDocument, OptionCircuit
)

verif_tel = RegexValidator(regex=r"^[0-9+\s\-().]{6,20}$", message=_("Numéro de téléphone invalide."))

# ─────────────────────────────────────────────────────────────
# Étape 0 — Choix du circuit
# ─────────────────────────────────────────────────────────────

class FormChoixCircuit(forms.Form):
    circuit = forms.ModelChoiceField(
        label=_("Circuit"),
        queryset=Circuit.objects.none(),
        help_text=_("Sélectionnez votre circuit."),
        empty_label=_("— Choisir —")
    )

    def __init__(self, *args, include_archived=False, force_include_circuit_id=None, **kwargs):
        super().__init__(*args, **kwargs)

        qs = Circuit.objects.all()

        if include_archived:
            # Staff : tout voir, pas besoin de forcer l’ID (il est déjà inclus)
            pass
        else:
            today = timezone.localdate()
            if force_include_circuit_id:
                # Un seul filtre avec OR — pas de union de QuerySets
                qs = qs.filter(
                    Q(statut="PUBLIE", date_fin__gte=today) |
                    Q(pk=force_include_circuit_id)
                )
            else:
                qs = qs.filter(statut="PUBLIE", date_fin__gte=today)

        self.fields["circuit"].queryset = qs.order_by("date_debut")


# ─────────────────────────────────────────────────────────────
# Étape 1 — Pilote (personne)
# ─────────────────────────────────────────────────────────────

class FormPilote(forms.Form):
    prenom = forms.CharField(label=_("Prénom"), max_length=80)
    nom = forms.CharField(label=_("Nom"), max_length=80)
    email = forms.EmailField(label=_("Email"))
    telephone = forms.CharField(label=_("Téléphone"), max_length=32, validators=[verif_tel])

    # ⬇️ ISO + input_formats
    date_naissance = forms.DateField(
        label="Date de naissance",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
    )

    numero_carte_identite = forms.CharField(label=_("N° passeport ou identité"), max_length=64, required=False)
    nationalite = forms.CharField(label=_("Nationalité"), max_length=80, required=False)

    adresse = forms.CharField(label=_("Adresse"), max_length=255, required=False)
    code_postal = forms.CharField(label=_("Code postal"), max_length=20, required=False)
    localite = forms.CharField(label=_("Localité"), max_length=80, required=False)
    pays = forms.CharField(label=_("Pays"), max_length=80, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # pas de localisation (sinon dd/mm/YYYY)
        self.fields["date_naissance"].localize = False
        v = self.initial.get("date_naissance")
        if isinstance(v, (_dt.date, _dt.datetime)):
            self.initial["date_naissance"] = v.strftime("%Y-%m-%d")

        placeholders = {
            "prenom": "Ex: Sophie",
            "nom": "Ex: DUPONT",
            "email": "Ex: sophie.dupont@example.be",
            "telephone": "Ex: +32 470 12 34 56",
            "date_naissance": "AAAA-MM-JJ",
            "numero_carte_identite": "Ex: Carte eID / Passeport (BE1234567)",
            "nationalite": "Ex: Belge",
            "adresse": "Ex: Rue de la Loi 16",
            "code_postal": "Ex: 1000",
            "localite": "Ex: Bruxelles",
            "pays": "Ex: Belgique",
        }

        for name, field in self.fields.items():
            ph = placeholders.get(name)
            if ph:
                field.widget.attrs.setdefault("placeholder", ph)

            # bonus UX
            if name == "email":
                field.widget.attrs.setdefault("autocomplete", "email")
            if name == "telephone":
                field.widget.attrs.setdefault("autocomplete", "tel")
                field.widget.attrs.setdefault("inputmode", "tel")
            if name == "code_postal":
                field.widget.attrs.setdefault("inputmode", "numeric")
            if name == "numero_carte_identite":
                field.widget.attrs.setdefault("autocomplete", "off")

        # (optionnel) classe commune
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " form-control").strip()


# === NOUVEAU : étape "infos médicales" ===
class FormInfosMedicales(forms.Form):
    groupe_sanguin = forms.ChoiceField(
        label=_("Groupe sanguin"),
        choices=[("", _("— Non renseigné —"))] + list(getattr(__import__("circuitMoto.models", fromlist=["GroupeSanguin"]), "GroupeSanguin").choices),
        required=False,
    )
    hta = forms.BooleanField(label=_("Hypertension artérielle"), required=False)
    asthme = forms.BooleanField(label=_("Asthme"), required=False)
    epilepsie = forms.BooleanField(label=_("Épilepsie"), required=False)
    problemes_peau = forms.BooleanField(label=_("Eczéma/irritations"), required=False)
    vertiges = forms.BooleanField(label=_("Vertiges"), required=False)
    notes = forms.CharField(label=_("Notes médicales"), widget=forms.Textarea(attrs={"rows":3}), required=False)    

# ─────────────────────────────────────────────────────────────
# Étape 2 — Moto
# ─────────────────────────────────────────────────────────────

class FormMoto(forms.Form):
    marque = forms.CharField(label=_("Marque"), max_length=80)
    modele = forms.CharField(label=_("Modèle"), max_length=80, required=False)
    immatriculation = forms.CharField(label=_("Immatriculation"), max_length=32, required=False)

# ─────────────────────────────────────────────────────────────
# Étape 3 — Passager (choix)
# ─────────────────────────────────────────────────────────────

class FormPassagerChoix(forms.Form):
    avec_passager = forms.BooleanField(label=_("Je voyage avec un passager"), required=False)

# ─────────────────────────────────────────────────────────────
# Étape 4 — Passager (si oui)
# ─────────────────────────────────────────────────────────────

class FormPassager(forms.Form):
    prenom = forms.CharField(label=_("Prénom du passager"), max_length=80)
    nom = forms.CharField(label=_("Nom du passager"), max_length=80)
    email = forms.EmailField(label=_("Email du passager"), required=False)
    telephone = forms.CharField(label=_("Téléphone du passager"), max_length=32, required=False, validators=[verif_tel])
    date_naissance = forms.DateField(label=_("Date de naissance"), required=False, widget=forms.DateInput(attrs={"type":"date"}))

    nationalite = forms.CharField(label=_("Nationalité"), max_length=80, required=False)
    numero_carte_identite = forms.CharField(label=_("N° passeport ou identité"), max_length=64, required=False)    

# ─────────────────────────────────────────────────────────────
# Étape 5 — Options du circuit (dynamiques selon le circuit + passager)
# ─────────────────────────────────────────────────────────────

def unit_price_help(price, currency):
    # localize() respecte la langue active (1 234,50 vs 1,234.50)
    return format_lazy(_("Prix unitaire : {price} {currency}"),
                       price=localize(price), currency=currency)


class FormOptions(forms.Form):
    """
    Construit dynamiquement des champs par option du circuit.
    - Si quantite_variable=False => case à cocher (0/1) => quantité=1
    - Si quantite_variable=True  => champ numérique avec min/max
    - Si facture_par_personne=True => on ajoute champs pilote (et passager si présent)
    """
    def __init__(self, *args, circuit: Optional[Circuit] = None, passager: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self._defs = []  # [(opt, field_name, for_passenger: Optional[bool])]
        if not circuit:
            return
        for opt in circuit.options.order_by("categorie", "code"):
            if opt.facture_par_personne:
                # Pilote
                fname = f"opt_{opt.pk}_pilote"
                if opt.quantite_variable:
                    self.fields[fname] = forms.IntegerField(
                        label=format_lazy("{title} — {role}", title=opt.intitule, role=_("Pilote")),
                        required=False,
                        min_value=max(1, opt.quantite_min or 1),
                        help_text=unit_price_help(opt.prix_unitaire, circuit.devise)

                    )
                else:
                    self.fields[fname] = forms.BooleanField(
                        label=format_lazy("{title} — {role}", title=opt.intitule, role=_("Pilote")),
                        required=False,
                        help_text=unit_price_help(opt.prix_unitaire, circuit.devise)

                    )
                self._defs.append((opt, fname, False))
                # Passager
                if passager:
                    fname2 = f"opt_{opt.pk}_passager"
                    if opt.quantite_variable:
                        self.fields[fname2] = forms.IntegerField(
                            label=format_lazy("{title} — {role}", title=opt.intitule, role=_("Passager")),
                            required=False,
                            min_value=max(1, opt.quantite_min or 1),
                            help_text=unit_price_help(opt.prix_unitaire, circuit.devise)

                        )
                    else:
                        self.fields[fname2] = forms.BooleanField(
                            label=format_lazy("{title} — {role}", title=opt.intitule, role=_("Passager")),
                            required=False,
                            help_text=unit_price_help(opt.prix_unitaire, circuit.devise)

                        )
                    self._defs.append((opt, fname2, True))
            else:
                fname = f"opt_{opt.pk}"
                if opt.quantite_variable:
                    self.fields[fname] = forms.IntegerField(
                        label=f"{opt.intitule}",
                        required=False,
                        min_value=max(1, opt.quantite_min or 1),
                        help_text=unit_price_help(opt.prix_unitaire, circuit.devise)

                    )
                else:
                    self.fields[fname] = forms.BooleanField(
                        label=f"{opt.intitule}",
                        required=False,
                        help_text=unit_price_help(opt.prix_unitaire, circuit.devise)

                    )
                self._defs.append((opt, fname, None))

    def extraire_selection(self) -> list:
        """
        Retourne une liste d'éléments:
        [{
          "option": OptionCircuit,
          "quantite": int,
          "pour_passager": bool
        }, ...]
        """
        result = []
        for opt, fname, for_pass in self._defs:
            val = self.cleaned_data.get(fname)
            if val in (None, False, 0, ""):
                continue
            if isinstance(self.fields[fname], forms.BooleanField):
                qte = 1 if val else 0
            else:
                qte = int(val)
            if qte > 0:
                result.append({"option": opt, "quantite": qte, "pour_passager": bool(for_pass) if for_pass is not None else False})
        return result

# ─────────────────────────────────────────────────────────────
# Étape 6 — Assurance
# ─────────────────────────────────────────────────────────────

class FormAssurance(forms.Form):
    type = forms.ChoiceField(label=_("Type d’assurance"), choices=TypeAssurance.choices)
    compagnie = forms.CharField(label=_("Compagnie"), max_length=120, required=False)
    numero_police = forms.CharField(label=_("N° de police"), max_length=120, required=False)

    # ⬇️ NOUVEAU
    telephone_urgence = forms.CharField(
        label=_("N° d’urgence (assureur)"),
        max_length=32,
        required=False,
        validators=[verif_tel]
    )


    # ⬇️ ISO + input_formats
    valide_du = forms.DateField(
        label="Valable du", required=False,
        widget=forms.DateInput(attrs={"type":"date"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
    )
    valide_au = forms.DateField(
        label="Valable au", required=False,
        widget=forms.DateInput(attrs={"type":"date"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("valide_du", "valide_au"):
            self.fields[name].localize = False
            v = self.initial.get(name)
            if isinstance(v, (_dt.date, _dt.datetime)):
                self.initial[name] = v.strftime("%Y-%m-%d")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("type") == TypeAssurance.DEJA_ASSURE and not cleaned.get("compagnie"):
            self.add_error("compagnie", _("La compagnie est requise si vous êtes déjà assuré."))
        d1, d2 = cleaned.get("valide_du"), cleaned.get("valide_au")
        if d1 and d2 and d2 < d1:
            self.add_error("valide_au", _("Période d’assurance invalide."))
        return cleaned

# ─────────────────────────────────────────────────────────────
# Étape 7 — Contacts d’urgence (2)
# ─────────────────────────────────────────────────────────────

class FormContactsUrgence(forms.Form):
    nom1 = forms.CharField(label=_("Contact 1 — Nom"), max_length=120)
    lien1 = forms.CharField(label=_("Contact 1 — Lien de parenté"), max_length=80, required=False)
    tel1 = forms.CharField(label=_("Contact 1 — Téléphone"), max_length=32, validators=[verif_tel])

    nom2 = forms.CharField(label=_("Contact 2 — Nom"), max_length=120)
    lien2 = forms.CharField(label=_("Contact 2 — Lien de parenté"), max_length=80, required=False)
    tel2 = forms.CharField(label=_("Contact 2 — Téléphone"), max_length=32, validators=[verif_tel])

# ─────────────────────────────────────────────────────────────
# Étape 8 — Documents
# ─────────────────────────────────────────────────────────────

class FormDocuments(forms.Form):
    MAX_MB = 1080  # choisis ta limite fonctionnelle

    cni = forms.FileField(required=False, label=_("Carte d’identité"))
    permis = forms.FileField(required=False, label=_("Permis de conduire"))
    carte_grise = forms.FileField(required=False, label=_("Carte grise"))
    attestation_assurance = forms.FileField(required=False, label=_("Attestation d’assurance"))
    certificat_medical = forms.FileField(required=False, label=_("Certificat médical"))

    def __init__(self, *args, **kwargs):
        is_edit = kwargs.pop("is_edit", False)
        existing_docs = kwargs.pop("existing_docs", {}) or {}
        super().__init__(*args, **kwargs)

        if is_edit:
            for f in self.fields.values():
                f.required = False

        # Conseils de sélection de fichier
        for f in self.fields.values():
            # types autorisés côté client (aide UX, non sécuritaire)
            f.widget.attrs["accept"] = ".pdf,.jpg,.jpeg,.png"
            # pour l’info dans le template / JS
            f.widget.attrs["data-max-mb"] = str(self.MAX_MB)

        # (inchangé) injection des métadonnées du fichier existant…
        for name, meta in existing_docs.items():
            if not meta:
                continue
            field = self.fields.get(name)
            if not field:
                continue
            w = field.widget
            w.attrs["data-existing"] = "1"
            w.attrs["data_existing"] = "1"
            w.attrs["data-existing-url"] = meta.get("url", "")
            w.attrs["data_existing_url"] = meta.get("url", "")
            w.attrs["data-existing-name"] = meta.get("name", "")
            w.attrs["data_existing_name"] = meta.get("name", "")
            w.attrs["data-existing-status"] = meta.get("status", "")
            w.attrs["data_existing_status"] = meta.get("status", "")

    def clean(self):
        cleaned = super().clean()
        max_bytes = self.MAX_MB * 1024 * 1024
        for name, f in cleaned.items():
            if hasattr(f, "size") and f.size and f.size > max_bytes:
                self.add_error(name, f"Fichier trop volumineux (> {self.MAX_MB} Mo).")
        return cleaned


# ─────────────────────────────────────────────────────────────
# Étape 9 — Décharge & signature
# ─────────────────────────────────────────────────────────────

class FormDecharge(forms.Form):
    accepter = forms.BooleanField(
        label=_("J’ai lu et j’accepte la décharge et les CGV"),
        required=True,
    )
    nom_signataire = forms.CharField(label="Nom du signataire", max_length=160)
    email_signataire = forms.EmailField(label="Email du signataire")
    # otp = forms.CharField(
    #     label="Code OTP (4 chiffres)", min_length=4, max_length=4,
    #     widget=forms.TextInput(attrs={
    #         "inputmode": "numeric", "pattern": r"\d{4}", "placeholder": "••••"
    #     })
    # )
    # ⬇️ image PNG encodée en base64 depuis le canvas
    signature_data = forms.CharField(widget=forms.HiddenInput(), required=False)

    # def clean_otp(self):
    #     v = self.cleaned_data["otp"]
    #     if not v.isdigit():
    #         raise forms.ValidationError("Le code OTP doit être numérique.")
    #     return v

from django import forms
from django.utils.translation import gettext_lazy as _
from .models import ContactMessage, Circuit, StatutCircuit, TypeDemande
import re


def _label_for(choice_enum, key):
    return dict(choice_enum.choices).get(key, key)


STATUT_CHOICES_CONTACT = [
    (StatutCircuit.PUBLIE, _label_for(StatutCircuit, StatutCircuit.PUBLIE)),
    (StatutCircuit.ARCHIVE, _label_for(StatutCircuit, StatutCircuit.ARCHIVE)),
]

# Détection simple des liens / domaines
URL_RE = re.compile(
    r'(https?://|www\.|[a-z0-9-]+\.(com|net|org|ru|xyz|top|click|info|biz|site|live)\b)',
    re.IGNORECASE
)

# Mots souvent utilisés dans les soumissions spam
SPAM_TERMS = [
    "promo code",
    "urgent message",
    "winning move",
    "loan",
    "casino",
    "crypto",
    "telegram",
    "whatsapp group",
    "seo service",
    "backlink",
    "traffic",
    "google ranking",
]


class ContactForm(forms.ModelForm):
    honeypot = forms.CharField(required=False, widget=forms.HiddenInput)

    statut_circuit = forms.ChoiceField(
        label=_("Statut du circuit"),
        required=False,
        choices=[("", "— " + _("Choisir") + " —")] + STATUT_CHOICES_CONTACT,
    )

    circuit = forms.ModelChoiceField(
        label=_("Circuit"),
        required=False,
        queryset=Circuit.objects.none()
    )

    interesse_circuit = forms.BooleanField(
        label=_("Intéressé par un circuit ?"),
        required=False
    )

    type_demande = forms.ChoiceField(
        label=_("Type de demande"),
        choices=TypeDemande.choices,
        initial=TypeDemande.INFO
    )

    consent = forms.BooleanField(
        label=_("J’accepte d’être contacté par Pulsion Horizon"),
        required=True
    )

    class Meta:
        model = ContactMessage
        fields = [
            "prenom", "nom", "email", "telephone", "adresse",
            "interesse_circuit", "statut_circuit", "circuit",
            "type_demande", "message", "consent",
        ]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        statut_init = (kwargs.pop("statut_init", "") or "").upper()
        super().__init__(*args, **kwargs)

        def add_cls(names, cls):
            for name in names:
                if name in self.fields:
                    w = self.fields[name].widget
                    w.attrs["class"] = (w.attrs.get("class", "") + " " + cls).strip()

        add_cls(["prenom", "nom", "email", "telephone", "adresse"], "form-input-luxury")
        add_cls(["message"], "form-textarea-luxury")
        add_cls(["type_demande", "statut_circuit", "circuit"], "form-select-luxury")

        self.fields["prenom"].widget.attrs.setdefault("placeholder", _("Votre prénom"))
        self.fields["nom"].widget.attrs.setdefault("placeholder", _("Votre nom"))
        self.fields["email"].widget.attrs.setdefault("placeholder", "email@example.com")
        self.fields["telephone"].widget.attrs.setdefault("placeholder", "+221 …")
        self.fields["adresse"].widget.attrs.setdefault("placeholder", _("Adresse complète"))

        if statut_init in dict(STATUT_CHOICES_CONTACT):
            self.fields["circuit"].queryset = Circuit.objects.filter(
                statut=statut_init
            ).order_by("-date_debut")

    def clean_honeypot(self):
        value = (self.cleaned_data.get("honeypot") or "").strip()
        if value:
            raise forms.ValidationError(_("Spam détecté."))
        return ""

    def clean_prenom(self):
        value = (self.cleaned_data.get("prenom") or "").strip()
        if len(value) < 2:
            raise forms.ValidationError(_("Prénom invalide."))
        if URL_RE.search(value):
            raise forms.ValidationError(_("Prénom invalide."))
        return value

    def clean_nom(self):
        value = (self.cleaned_data.get("nom") or "").strip()
        if len(value) < 2:
            raise forms.ValidationError(_("Nom invalide."))
        if URL_RE.search(value):
            raise forms.ValidationError(_("Nom invalide."))
        return value

    def clean_telephone(self):
        value = (self.cleaned_data.get("telephone") or "").strip()
        if not value:
            return value

        # Autorise chiffres, espaces, +, parenthèses, tirets
        if not re.fullmatch(r"[\d\+\s\-\(\)\.]{6,25}", value):
            raise forms.ValidationError(_("Numéro de téléphone invalide."))
        return value

    def clean_adresse(self):
        value = (self.cleaned_data.get("adresse") or "").strip()
        if value and URL_RE.search(value):
            raise forms.ValidationError(_("Adresse invalide."))
        return value

    def clean_message(self):
        msg = (self.cleaned_data.get("message") or "").strip()

        if len(msg) < 10:
            raise forms.ValidationError(_("Message trop court (10 caractères minimum)."))

        if len(msg) > 3000:
            raise forms.ValidationError(_("Message trop long."))

        lowered = msg.lower()

        if URL_RE.search(msg):
            raise forms.ValidationError(_("Les liens ne sont pas autorisés dans le formulaire de contact."))

        if any(term in lowered for term in SPAM_TERMS):
            raise forms.ValidationError(_("Message refusé."))

        return msg

    def clean(self):
        data = super().clean()

        if data.get("interesse_circuit"):
            if not data.get("statut_circuit"):
                self.add_error("statut_circuit", _("Choisissez un statut."))
            if not data.get("circuit"):
                self.add_error("circuit", _("Choisissez un circuit."))

        return data
    

# =========================
# BALADES 1 JOUR
# =========================
from django import forms
from .models import BaladeJour, DemandeProgrammeBalade


class BaladesCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    template_name = "django/forms/widgets/checkbox_select.html"
    option_template_name = "django/forms/widgets/checkbox_option.html"


class DemandeProgrammeBaladeForm(forms.ModelForm):
    balades = forms.ModelMultipleChoiceField(
        label="Balades qui m’intéressent",
        queryset=BaladeJour.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    website = forms.CharField(required=False, widget=forms.HiddenInput)
    company = forms.CharField(required=False, widget=forms.HiddenInput)
    ts = forms.IntegerField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = DemandeProgrammeBalade
        fields = ["prenom", "nom", "email", "telephone", "commentaire", "balades"]
        widgets = {
            "prenom": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Votre prénom",
                "autocomplete": "given-name",
            }),
            "nom": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Votre nom",
                "autocomplete": "family-name",
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": "Votre e-mail",
                "autocomplete": "email",
            }),
            "telephone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Votre téléphone (facultatif)",
                "autocomplete": "tel",
            }),
            "commentaire": forms.Textarea(attrs={
                "class": "form-control",
                "placeholder": "Une précision ?",
                "rows": 4,
            }),
        }

    def __init__(self, *args, **kwargs):
        balades_queryset = kwargs.pop("balades_queryset", None)
        super().__init__(*args, **kwargs)

        if balades_queryset is None:
            balades_queryset = BaladeJour.objects.filter(actif=True).order_by("date_debut", "ordre", "titre")

        self.fields["balades"].queryset = balades_queryset

    def clean_website(self):
        value = (self.cleaned_data.get("website") or "").strip()
        if value:
            raise forms.ValidationError("Soumission invalide.")
        return value

    def clean_company(self):
        value = (self.cleaned_data.get("company") or "").strip()
        if value:
            raise forms.ValidationError("Soumission invalide.")
        return value

    def clean_commentaire(self):
        value = (self.cleaned_data.get("commentaire") or "").strip()

        lowered = value.lower()
        banned_patterns = [
            "http://", "https://", "[url", "viagra", "crypto", "seo", "backlink", "telegram", "whatsapp:",
        ]
        if any(p in lowered for p in banned_patterns):
            raise forms.ValidationError("Message refusé.")
        if len(value) > 1500:
            raise forms.ValidationError("Message trop long.")
        return value

    def clean_balades(self):
        balades = self.cleaned_data.get("balades")
        if not balades:
            raise forms.ValidationError("Merci de sélectionner au moins une balade.")
        return balades


# =========================
# PRE PROGRAMME 2027
# =========================
from .models import (
    Programme2027Circuit,
    Programme2027Interest,
)


class Programme2027InterestForm(forms.ModelForm):
    circuits = forms.ModelMultipleChoiceField(
        label="Circuits qui m'interessent",
        queryset=Programme2027Circuit.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    website = forms.CharField(required=False, widget=forms.HiddenInput)
    company = forms.CharField(required=False, widget=forms.HiddenInput)
    ts = forms.IntegerField(required=False, widget=forms.HiddenInput)

    consent = forms.BooleanField(
        label="J'accepte d'etre contacte par Pulsion Horizon au sujet du programme 2027",
        required=True,
    )
    newsletter_optin = forms.BooleanField(
        label="Je souhaite recevoir les informations et ouvertures de reservations",
        required=False,
    )

    class Meta:
        model = Programme2027Interest
        fields = [
            "prenom", "nom", "email", "telephone",
            "commentaire", "consent", "newsletter_optin", "circuits",
        ]
        widgets = {
            "prenom": forms.TextInput(attrs={
                "class": "p27-input",
                "placeholder": "Votre prenom",
                "autocomplete": "given-name",
            }),
            "nom": forms.TextInput(attrs={
                "class": "p27-input",
                "placeholder": "Votre nom",
                "autocomplete": "family-name",
            }),
            "email": forms.EmailInput(attrs={
                "class": "p27-input",
                "placeholder": "email@example.com",
                "autocomplete": "email",
            }),
            "telephone": forms.TextInput(attrs={
                "class": "p27-input",
                "placeholder": "+32 ...",
                "autocomplete": "tel",
            }),
            "commentaire": forms.Textarea(attrs={
                "class": "p27-input p27-textarea",
                "placeholder": "Une question ou une préférence ?",
                "rows": 4,
            }),
        }

    def __init__(self, *args, **kwargs):
        circuits_queryset = kwargs.pop("circuits_queryset", None)
        super().__init__(*args, **kwargs)

        if circuits_queryset is None:
            circuits_queryset = Programme2027Circuit.objects.filter(actif=True).order_by("ordre", "titre")

        self.fields["circuits"].queryset = circuits_queryset

    def clean_website(self):
        value = (self.cleaned_data.get("website") or "").strip()
        if value:
            raise forms.ValidationError("Soumission invalide.")
        return value

    def clean_company(self):
        value = (self.cleaned_data.get("company") or "").strip()
        if value:
            raise forms.ValidationError("Soumission invalide.")
        return value

    def clean_prenom(self):
        value = (self.cleaned_data.get("prenom") or "").strip()
        if len(value) < 2 or URL_RE.search(value):
            raise forms.ValidationError("Prenom invalide.")
        return value

    def clean_nom(self):
        value = (self.cleaned_data.get("nom") or "").strip()
        if len(value) < 2 or URL_RE.search(value):
            raise forms.ValidationError("Nom invalide.")
        return value

    def clean_commentaire(self):
        value = (self.cleaned_data.get("commentaire") or "").strip()
        lowered = value.lower()
        banned_patterns = [
            "http://", "https://", "[url", "viagra", "crypto", "seo",
            "backlink", "telegram", "whatsapp:",
        ]
        if any(p in lowered for p in banned_patterns):
            raise forms.ValidationError("Message refuse.")
        if len(value) > 1800:
            raise forms.ValidationError("Message trop long.")
        return value

    def clean_circuits(self):
        circuits = self.cleaned_data.get("circuits")
        if not circuits:
            raise forms.ValidationError("Merci de selectionner au moins un circuit.")
        return circuits
