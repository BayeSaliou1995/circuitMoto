# -*- coding: utf-8 -*-
"""Formulaires du back-office."""
from __future__ import annotations

import datetime
import re
from decimal import Decimal
from typing import List, Tuple

from django import forms  # type: ignore
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import (
    ValidationError as PwValidationError,
    validate_password,
)
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.forms import formset_factory, inlineformset_factory
from django.utils import timezone
from django.utils.text import slugify

from ..models import (
    Circuit,
    ContactUrgence,
    InfosMedicales,
    OptionCircuit,
    Personne,
    StatutInscription,
)

EMAIL_SPLIT_RE = re.compile(r"[,;\s]+")


def parse_emails_blob(raw: str) -> Tuple[List[str], List[str]]:
    if not raw:
        return [], []

    candidates = [item.strip() for item in EMAIL_SPLIT_RE.split(raw) if item.strip()]
    valid_emails: List[str] = []
    invalid_emails: List[str] = []
    seen = set()

    for email in candidates:
        email_norm = email.lower()
        try:
            validate_email(email_norm)
            if email_norm not in seen:
                seen.add(email_norm)
                valid_emails.append(email_norm)
        except ValidationError:
            invalid_emails.append(email)

    return valid_emails, invalid_emails


class MultipleFilesInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class NewsletterBroadcastForm(forms.Form):
    emails_blob = forms.CharField(
        label="Emails des destinataires",
        widget=forms.Textarea(attrs={
            "rows": 12,
            "placeholder": (
                "Collez ici les emails séparés par virgules, points-virgules ou retours à la ligne.\n"
                "Exemple :\n"
                "client1@email.com\n"
                "client2@email.com; client3@email.com, client4@email.com"
            ),
        }),
    )
    sujet = forms.CharField(max_length=180, label="Sujet")
    message = forms.CharField(label="Message", widget=forms.Textarea(attrs={"rows": 12}))
    test_only = forms.BooleanField(required=False, initial=False, label="N’envoyer qu’à moi (test)")
    pieces_jointes = forms.FileField(
        label="Pièces jointes",
        required=False,
        widget=MultipleFilesInput(attrs={"multiple": True}),
    )

    def clean_pieces_jointes(self):
        max_attachment_bytes = int(getattr(settings, "NEWSLETTER_MAX_ATTACHMENT_BYTES", 25 * 1024 * 1024))
        files = self.files.getlist("pieces_jointes")
        if sum(f.size for f in files) > max_attachment_bytes:
            raise forms.ValidationError("Le poids total des pièces jointes dépasse la limite autorisée.")
        return files

    def clean_emails_blob(self):
        raw = self.cleaned_data.get("emails_blob", "")
        max_recipients = int(getattr(settings, "NEWSLETTER_MAX_RECIPIENTS_PER_SEND", 1500))
        valid_emails, invalid_emails = parse_emails_blob(raw)
        self._parsed_valid_emails = valid_emails
        self._parsed_invalid_emails = invalid_emails
        if not valid_emails:
            raise forms.ValidationError("Aucune adresse e-mail valide détectée.")
        if len(valid_emails) > max_recipients:
            raise forms.ValidationError("Le nombre d’adresses dépasse la limite autorisée.")
        return raw

    def get_valid_emails(self) -> List[str]:
        return getattr(self, "_parsed_valid_emails", [])

    def get_invalid_emails(self) -> List[str]:
        return getattr(self, "_parsed_invalid_emails", [])


class PaymentSummaryComposeForm(forms.Form):
    ins_id = forms.IntegerField(widget=forms.HiddenInput())
    recipient_role = forms.ChoiceField(choices=(("pilote", "Pilote"), ("passager", "Passager")))
    sujet = forms.CharField(max_length=180, label="Sujet")
    intro_message = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
    total_attendu = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, label="Total attendu initial")
    montant_options_ajoutees = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, initial=Decimal("0.00"))
    nouveau_total_attendu = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    acompte1_encaisse = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, initial=Decimal("0.00"))
    acompte2_encaisse = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, initial=Decimal("0.00"))
    solde_encaisse = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, initial=Decimal("0.00"))
    paiement_recu_pour_options = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, initial=Decimal("0.00"))
    date_paiement = forms.DateField(required=True, initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
    montant_restant = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    trop_percu = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    situation_label = forms.CharField(max_length=120, required=False)
    inclure_detail_paiements = forms.BooleanField(required=False, initial=True)
    inclure_infos_paiement = forms.BooleanField(required=False, initial=True)
    infos_paiement_custom = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 5}))
    note_client = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 5}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _, field in self.fields.items():
            widget = field.widget
            css = widget.attrs.get("class", "")
            if isinstance(widget, forms.TextInput):
                widget.attrs["class"] = f"{css} paysum-input".strip()
            elif isinstance(widget, forms.Textarea):
                widget.attrs["class"] = f"{css} paysum-textarea".strip()
            elif isinstance(widget, forms.Select):
                widget.attrs["class"] = f"{css} paysum-select".strip()
            elif isinstance(widget, forms.NumberInput):
                widget.attrs["class"] = f"{css} paysum-input paysum-input--number".strip()
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = f"{css} paysum-checkbox".strip()
        for name in (
            "total_attendu", "montant_options_ajoutees", "nouveau_total_attendu",
            "acompte1_encaisse", "acompte2_encaisse", "solde_encaisse",
            "paiement_recu_pour_options", "montant_restant", "trop_percu",
        ):
            self.fields[name].widget.attrs.update({"step": "0.01", "inputmode": "decimal"})
        for name in ("nouveau_total_attendu", "montant_restant", "trop_percu"):
            self.fields[name].widget.attrs.update({"readonly": True, "data-auto-computed": "1"})

    def clean(self):
        cleaned = super().clean()
        total_attendu = cleaned.get("total_attendu") or Decimal("0")
        montant_options_ajoutees = cleaned.get("montant_options_ajoutees") or Decimal("0")
        acompte1 = cleaned.get("acompte1_encaisse") or Decimal("0")
        acompte2 = cleaned.get("acompte2_encaisse") or Decimal("0")
        solde = cleaned.get("solde_encaisse") or Decimal("0")
        paiement_options = cleaned.get("paiement_recu_pour_options") or Decimal("0")

        nouveau_total = total_attendu + montant_options_ajoutees
        cleaned["nouveau_total_attendu"] = nouveau_total
        total_saisi = acompte1 + acompte2 + solde + paiement_options

        if total_saisi <= Decimal("0"):
            raise forms.ValidationError("Merci de saisir au moins un montant encaissé.")

        montant_restant = Decimal("0")
        trop_percu = Decimal("0")
        situation_label = "Soldé"
        if total_saisi < nouveau_total:
            montant_restant = nouveau_total - total_saisi
            situation_label = "Reste à payer"
        elif total_saisi > nouveau_total:
            trop_percu = total_saisi - nouveau_total
            situation_label = "Trop-perçu"

        cleaned["total_deja_paye_calcule"] = total_saisi
        cleaned["montant_restant"] = montant_restant
        cleaned["trop_percu"] = trop_percu
        if not cleaned.get("situation_label"):
            cleaned["situation_label"] = "Paiement reçu après ajout d’options" if montant_options_ajoutees > 0 and paiement_options > 0 else situation_label
        return cleaned


class CircuitForm(forms.ModelForm):
    image = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={"accept": "image/*"}))
    date_debut = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), input_formats=["%Y-%m-%d", "%d/%m/%Y"])
    date_fin = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), input_formats=["%Y-%m-%d", "%d/%m/%Y"])

    class Meta:
        model = Circuit
        fields = [
            "nom", "code", "image", "date_debut", "date_fin", "description", "infos_rdv",
            "capacite", "devise", "prix_pilote_unitaire", "prix_passager_unitaire",
            "delai_option_jours", "statut",
            "acompte1_par_personne", "acompte2_par_personne",
            "delai_acompte2_jours", "delai_solde_jours",
            "programme", "kilometrages", "prix_comprend", "prix_ne_comprend_pas",
            "echeancier_texte", "infos_paiement",
            "itineraire_active", "itineraire_points", "itineraire_google_maps_url",
            "itineraire_embed_url", "itineraire_street_view_url",
            "email_rdv", "email_organisation", "email_checklist",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "infos_rdv": forms.Textarea(attrs={"rows": 3}),
            "infos_paiement": forms.Textarea(attrs={"rows": 4}),
            "itineraire_points": forms.Textarea(attrs={
                "rows": 12,
                "spellcheck": "false",
                "placeholder": (
                    '[{"day":"Jour 1","title":"Las Vegas","points":['
                    '{"label":"Las Vegas","lat":36.1699,"lng":-115.1398},'
                    '{"label":"Zion","lat":37.2982,"lng":-113.0263}'
                    '],"street_view":{"lat":36.1699,"lng":-115.1398,"heading":80}}]'
                ),
            }),
            "email_rdv": forms.Textarea(attrs={"rows": 3}),
            "email_organisation": forms.Textarea(attrs={"rows": 3}),
            "email_checklist": forms.Textarea(attrs={"rows": 6}),
        }

    def clean_image(self):
        img = self.cleaned_data.get("image")
        if img and img.size > 8 * 1024 * 1024:
            raise forms.ValidationError("Image trop volumineuse (max 8 Mo).")
        return img

    def clean_itineraire_points(self):
        data = self.cleaned_data.get("itineraire_points") or []
        if data in ("", None):
            return []
        if not isinstance(data, list):
            raise forms.ValidationError("Le JSON doit être une liste de jours.")
        for index, day in enumerate(data, start=1):
            if not isinstance(day, dict):
                raise forms.ValidationError(f"L'entrée {index} doit être un objet JSON.")
            points = day.get("points") or day.get("stops") or day.get("etapes") or []
            if points and not isinstance(points, list):
                raise forms.ValidationError(f"Les points du jour {index} doivent être une liste.")
        return data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("date_debut", "date_fin"):
            self.fields[name].localize = False
            self.fields[name].widget.is_localized = False
        if not self.data:
            for name in ("date_debut", "date_fin"):
                val = getattr(self.instance, name, None)
                if isinstance(val, (datetime.date, datetime.datetime)):
                    self.initial[name] = val.strftime("%Y-%m-%d")

    def clean(self):
        cleaned = super().clean()
        dd, df = cleaned.get("date_debut"), cleaned.get("date_fin")
        if dd and df and df < dd:
            self.add_error("date_fin", "La date de fin doit être ≥ la date de début.")
        if cleaned.get("itineraire_active"):
            has_data = bool(cleaned.get("itineraire_points")) or bool(cleaned.get("itineraire_google_maps_url")) or bool(cleaned.get("itineraire_embed_url"))
            if not has_data:
                self.add_error("itineraire_active", "Ajoutez au moins un JSON d'itinéraire, un lien Google Maps ou une URL d'intégration.")
        return cleaned


class OptionForm(forms.ModelForm):
    class Meta:
        model = OptionCircuit
        fields = [
            "code", "intitule", "categorie", "prix_unitaire",
            "facture_par_personne", "quantite_variable", "quantite_min", "quantite_max", "actif",
        ]
        widgets = {
            "code": forms.TextInput(attrs={"placeholder": "ex: cabine-2lits"}),
            "intitule": forms.TextInput(attrs={"placeholder": "Ex: Cabine 2 lits"}),
            "prix_unitaire": forms.NumberInput(attrs={"step": "1", "min": "0"}),
        }

    def clean(self):
        cleaned = super().clean()
        code = cleaned.get("code") or ""
        intitule = cleaned.get("intitule") or ""
        qmin = cleaned.get("quantite_min") or 0
        qmax = cleaned.get("quantite_max") or 0
        if not code and intitule:
            cleaned["code"] = slugify(intitule)
        if qmax and qmin and qmax < qmin:
            self.add_error("quantite_max", "La quantité max doit être ≥ min (ou 0 pour illimité).")
        return cleaned


OptionFormSet = inlineformset_factory(
    parent_model=Circuit,
    model=OptionCircuit,
    form=OptionForm,
    fields=[
        "code", "intitule", "categorie", "prix_unitaire",
        "facture_par_personne", "quantite_variable", "quantite_min", "quantite_max",
    ],
    extra=0,
    can_delete=True,
)


class EmailingForm(forms.Form):
    circuit = forms.ModelChoiceField(queryset=Circuit.objects.all().order_by("-date_debut"), required=False)
    statut = forms.ChoiceField(choices=[("", "— Tous statuts —")] + list(StatutInscription.choices), required=False)
    inclure_passagers = forms.BooleanField(required=False, initial=True)
    sujet = forms.CharField(max_length=180)
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 8}))
    test_only = forms.BooleanField(required=False, initial=False)
    pieces_jointes = forms.FileField(required=False, widget=MultipleFilesInput(attrs={"multiple": True}))

    def clean_pieces_jointes(self):
        files = self.files.getlist("pieces_jointes")
        max_size = 25 * 1024 * 1024
        for f in files:
            if f.size > max_size:
                raise forms.ValidationError(f"“{f.name}” est trop volumineux (> 25 Mo).")
        return files


class PersonneForm(forms.ModelForm):
    class Meta:
        model = Personne
        fields = [
            "prenom", "nom", "email", "telephone",
            "date_naissance", "numero_carte_identite",
            "adresse", "code_postal", "localite", "pays",
        ]
        widgets = {
            "date_naissance": forms.DateInput(attrs={"type": "date"}),
            "adresse": forms.Textarea(attrs={"rows": 2, "placeholder": "Rue, N°, compléments…"}),
        }


class InfosMedicalesForm(forms.ModelForm):
    class Meta:
        model = InfosMedicales
        exclude = ("personne",)
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class SimpleMotoForm(forms.Form):
    marque = forms.CharField(max_length=80, required=False)
    modele = forms.CharField(max_length=80, required=False)
    immatriculation = forms.CharField(max_length=32, required=False)

    def has_any_data(self):
        return any(self.cleaned_data.get(k) for k in ["marque", "modele", "immatriculation"])


MotoFormSet = formset_factory(SimpleMotoForm, extra=1, can_delete=True)


class SimpleContactUrgenceForm(forms.Form):
    nom = forms.CharField(max_length=120, required=False)
    lien_parente = forms.CharField(max_length=80, required=False)
    telephone = forms.CharField(max_length=32, required=False)

    def has_any_data(self):
        return any(self.cleaned_data.get(k) for k in ["nom", "telephone", "lien_parente"])


ContactUrgenceFormSet = formset_factory(SimpleContactUrgenceForm, extra=2, can_delete=True)


class StaffUserCreateForm(forms.ModelForm):
    is_superuser = forms.BooleanField(required=False, initial=False, label="Administrateur (superuser)")

    class Meta:
        model = get_user_model()
        fields = ["username", "email", "first_name", "last_name"]

    def clean_email(self):
        e = (self.cleaned_data.get("email") or "").strip()
        if not e:
            raise forms.ValidationError("Email requis.")
        if get_user_model().objects.filter(email__iexact=e).exists():
            raise forms.ValidationError("Un utilisateur avec cet email existe déjà.")
        return e


class FirstPasswordChangeForm(forms.Form):
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}), label="Nouveau mot de passe")
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}), label="Confirmer")

    def clean(self):
        c = super().clean()
        p1, p2 = c.get("password1") or "", c.get("password2") or ""
        if p1 != p2:
            self.add_error("password2", "Les deux mots de passe ne correspondent pas.")
        try:
            validate_password(p1)
        except PwValidationError as e:
            self.add_error("password1", " ".join(e.messages))
        return c


class SelfPasswordChangeForm(forms.Form):
    current_password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))
    new_password1 = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    new_password2 = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_current_password(self):
        cur = self.cleaned_data.get("current_password") or ""
        if not self.user.check_password(cur):
            raise forms.ValidationError("Mot de passe actuel incorrect.")
        return cur

    def clean(self):
        c = super().clean()
        p1, p2 = c.get("new_password1") or "", c.get("new_password2") or ""
        if p1 != p2:
            self.add_error("new_password2", "Les deux mots de passe ne correspondent pas.")
        try:
            validate_password(p1, user=self.user)
        except PwValidationError as e:
            self.add_error("new_password1", " ".join(e.messages))
        return c
