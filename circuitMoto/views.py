# circuitMoto/views.py
# -*- coding: utf-8 -*-
from typing import Optional, List, Dict
import os
import uuid
from django.shortcuts import redirect
from django.conf import settings # type: ignore
from django.core.files.storage import FileSystemStorage # type: ignore
from django.db.models import Count #type: ignore
from django.shortcuts import render, get_object_or_404 # type: ignore
from django.utils import timezone # type: ignore
from formtools.wizard.views import SessionWizardView # type: ignore
from django.core.exceptions import PermissionDenied # type: ignore
from formtools.wizard.views import NamedUrlSessionWizardView #type: ignore
from django.urls import reverse #type: ignore
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.http import Http404
from django.core.files.base import ContentFile
import base64, re
import secrets
from django.http import HttpResponseBase
from django.core.paginator import Paginator
from django.contrib import messages
from django.views.generic import ListView
from django.db.models import Q
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from collections import defaultdict
from django.db.models import Count, F, Q
from django.core.paginator import Paginator
from django.utils import timezone
import re
from collections import defaultdict
from django.db.models import Count, Prefetch
from datetime import timedelta
from urllib.parse import quote
from .models import OptionCircuit
from django.core.paginator import Paginator
from django.utils import timezone
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.translation import gettext as _
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
import hashlib
from .forms import ContactForm, Programme2027InterestForm
from .models import Circuit, StatutCircuit, ContactMessage

from django.views.decorators.http import require_http_methods
from django.db import transaction

from .forms import DemandeProgrammeBaladeForm
from .models import BaladeJour, DemandeProgrammeBalade
from .emails import (
    notify_demande_balades_admin,
    notify_demande_balades_user_ack,
    notify_programme_2027_admin,
    notify_programme_2027_user_ack,
)


from .forms import (
    FormChoixCircuit, FormPilote, FormInfosMedicales, FormMoto, FormPassagerChoix, FormPassager,
    FormOptions, FormAssurance, FormContactsUrgence, FormDocuments, FormDecharge
)

from .models import (
    Circuit, Personne, Moto as MotoModel, Inscription, SelectionOption,
    Assurance as AssuranceModel, ContactUrgence, Document, TypeDocument,
    DechargeSignee, initialiser_plan_paiement_par_defaut, InfosMedicales,
    NewsletterSubscriber, StatutCircuit, SiteVisitor, Paiement, LibellePaiement,
    recalculer_plan_paiement_en_conservant_encaissements,
    NiveauInteret2027, Programme2027Circuit, Programme2027Selection,
)

from .emails import notify_inscription_recue

def _norm_email(s: str) -> str:
    return (s or "").strip().lower()

def _norm_tel(s: str) -> str:
    return (s or "").strip()

def _fill_if_blank(person, data: dict, fields: List[str]) -> bool:
    """
    Recopie dans `person` les champs manquants uniquement (si vides).
    Retourne True si au moins un champ a été modifié.
    """
    changed = False
    for f in fields:
        v = data.get(f)
        if v and not getattr(person, f):
            setattr(person, f, v)
            changed = True
    return changed

# Stockage temporaire pour les fichiers wizard
_tmp_media = os.path.join(settings.MEDIA_ROOT, "tmp_wizard")
os.makedirs(_tmp_media, exist_ok=True)
file_storage = FileSystemStorage(location=_tmp_media)

def _get_selected_circuit_from_wizard(view):
    """
    Récupère le Circuit de manière robuste :
    1) cleaned_data_for_step("circuit")
    2) re-valide le form 'circuit' à partir des données stockées (storage)
    3) fallback édition : view.inscription.circuit
    """
    # 1) cleaned_data normal
    d = view.get_cleaned_data_for_step("circuit") or {}
    c = d.get("circuit")
    if c:
        return c

    # 2) Revalider depuis le storage (au cas où cleaned_data ne remonte pas)
    try:
        step_data = view.storage.get_step_data("circuit")
        if step_data:
            f = view.get_form(step="circuit", data=step_data)
            if f.is_valid():
                return f.cleaned_data.get("circuit")
    except Exception:
        pass

    # 3) Edition : fallback circuit existant
    ins = getattr(view, "inscription", None)
    if ins and getattr(ins, "circuit_id", None):
        return ins.circuit

    return None

def _get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()

def home(request):
    today = timezone.localdate()

    # ---- Compteur visiteurs ----
    if not request.session.session_key:
        request.session.save()

    session_key = request.session.session_key or ""
    ip = _get_client_ip(request)

    # On compte une seule fois par session sur la home
    visitor_seen_key = "home_visitor_counted"

    if not request.session.get(visitor_seen_key, False):
        SiteVisitor.objects.create(
            ip=ip or None,
            session_key=session_key,
            path=request.path[:255],
        )
        request.session[visitor_seen_key] = True

    total_visitors = SiteVisitor.objects.count()
    is_new_feature = total_visitors < 1000

    # ---- paramètres GET (avec valeurs par défaut) ----
    q = (request.GET.get("q") or "").strip()
    from_date = (request.GET.get("from") or today.isoformat())
    sort = (request.GET.get("sort") or "date")

    # ---- base queryset : circuits publiés et à venir dès from_date ----
    qs = (
        Circuit.objects
        .filter(statut=StatutCircuit.PUBLIE, date_debut__gte=from_date)
        .annotate(nb_inscriptions=Count("inscriptions"))
        .prefetch_related("options")
    )

    # ---- recherche plein-texte simple (ICONTains) ----
    if q:
        qs = qs.filter(
            Q(nom__icontains=q) |
            Q(code__icontains=q) |
            Q(infos_rdv__icontains=q) |
            Q(description__icontains=q)
        )

    # ---- tris serveur cohérents avec tes options UI ----
    qs = qs.annotate(places_dispos=F("capacite") - F("nb_inscriptions"))

    if sort == "price_asc":
        qs = qs.order_by("prix_pilote_unitaire", "date_debut")
    elif sort == "price_desc":
        qs = qs.order_by("-prix_pilote_unitaire", "date_debut")
    elif sort == "capacity":
        qs = qs.order_by("-places_dispos", "date_debut")
    else:
        qs = qs.order_by("date_debut")

    # ---- pagination APRES filtrage/tri ----
    paginator = Paginator(qs, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    page_range = paginator.get_elided_page_range(
        number=page_obj.number, on_each_side=1, on_ends=1
    )

    # ---- querystring sans 'page' pour la pagination ----
    base_qs = request.GET.copy()
    if "page" in base_qs:
        del base_qs["page"]
    qs_no_page = base_qs.urlencode()

    # ---- KPIs existants ----
    ins_count = Inscription.objects.count()
    passager_count = Inscription.objects.filter(passager__isnull=False).count()
    total_participants = ins_count + passager_count

    return render(
        request,
        "circuitMoto/home.html",
        {
            "today": today,
            "q": q,
            "from_date": from_date,
            "sort": sort,
            "page_obj": page_obj,
            "page_range": page_range,
            "circuits": page_obj.object_list,
            "qs_no_page": qs_no_page,
            "circuits_total_upcoming": paginator.count,
            "total_inscrits": total_participants,

            # ✅ visiteurs
            "total_visitors": total_visitors,
            "is_new_feature": is_new_feature,
        },
    )

def afficher_passager(wizard):
    """
    Condition pour l'étape 'passager'.
    - En création : tant que 'passager_choix' n'est pas rempli -> False (hide)
    - En édition : défaut = en fonction de l'inscription existante
    """
    choix = wizard.get_cleaned_data_for_step("passager_choix")
    if choix is None:
        ins = getattr(wizard, "inscription", None)
        return bool(ins and ins.passager_id)
    return bool(choix.get("avec_passager"))

def _render_decharge_html(circuit, pilote_prenom="", pilote_nom=""):
    if not circuit:
        return ""
    today = timezone.localdate()
    return render_to_string(
        "circuitMoto/inscription/_decharge_contenu.html",
        {"circuit": circuit, "pilote_prenom": pilote_prenom, "pilote_nom": pilote_nom, "today": today}
    )

# TEMPLATES par étape
TEMPLATES = {
    "circuit": "circuitMoto/inscription/step_circuit.html",
    "pilote": "circuitMoto/inscription/step_pilote.html",
    "infos_med": "circuitMoto/inscription/step_infos_medicales.html",
    "moto": "circuitMoto/inscription/step_moto.html",
    "passager_choix": "circuitMoto/inscription/step_passager_choix.html",
    "passager": "circuitMoto/inscription/step_passager.html",
    "options": "circuitMoto/inscription/step_options.html",
    "assurance": "circuitMoto/inscription/step_assurance.html",
    "contacts": "circuitMoto/inscription/step_contacts.html",
    "documents": "circuitMoto/inscription/step_documents.html",
    "decharge": "circuitMoto/inscription/step_decharge.html",
}

# === Helpers affichage "succès" ===
def _acompte_par_personne(circuit) -> int:
    """
    Montant d'acompte par personne.
    • Si le modèle Circuit a un champ 'acompte_par_personne', on l'utilise.
    • Sinon fallback : 250 € pour la Corse, 0 € sinon.
    """
    val = getattr(circuit, "acompte_par_personne", None)
    if isinstance(val, (int, float)) and val > 0:
        return int(val)
    code = (getattr(circuit, "code", "") or "").lower()
    if "corse" in code:
        return 250
    return 0

def _build_success_context(inscription) -> dict:
    # personnes
    nb_personnes = 1 + (1 if getattr(inscription, "passager_id", None) else 0)

    # options total (robuste si prix_total est une @property)
    opt_total = 0
    for s in inscription.selections_options.all():
        try:
            opt_total += (s.prix_total or 0)
        except Exception:
            opt_total += (getattr(s, "prix_unitaire_fige", 0) or 0) * (getattr(s, "quantite", 0) or 0)

    # base + total
    prix_pilote  = getattr(inscription, "prix_pilote_unitaire", 0) or 0
    prix_passager = getattr(inscription, "prix_passager_unitaire", 0) or 0
    base = prix_pilote + prix_passager
    total = base + opt_total

    # acompte (on détecte un éventuel paiement d'acompte existant)
    acompte_qs = inscription.paiements.filter(libelle__in=["ACOMPTE1", "ACOMPTE"]).order_by("encaisse_le", "echeance_le")
    acompte1 = acompte_qs.first()
    acompte_par_pers = _acompte_par_personne(inscription.circuit)
    acompte_estime = acompte_par_pers * nb_personnes if acompte_par_pers else 0

    acompte_paye = bool(acompte1 and (getattr(acompte1, "encaisse_le", None) or str(getattr(acompte1, "statut", "")).upper() in {"VALIDE","PAYE","REGLE"}))
    acompte_montant = (getattr(acompte1, "montant_du", None) or acompte_estime) or 0
    acompte_date = getattr(acompte1, "encaisse_le", None)

    # solde (échéance du reste à payer)
    solde = inscription.paiements.filter(libelle="SOLDE").first()
    solde_date = getattr(solde, "echeance_le", None)

    return {
        "pricing": {
            "nb_personnes": nb_personnes,
            "pilote": prix_pilote,
            "passager": prix_passager,  # 0 s'il n'y a pas de passager
            "options_total": opt_total,
            "base": base,
            "total": total,
        },
        "echeancier": {
            "acompte": {
                "paye": acompte_paye,
                "montant": acompte_montant,
                "date": acompte_date,
                "par_personne": acompte_par_pers,
                "nb_personnes": nb_personnes,
            },
            "solde": {
                "date": solde_date,
            }
        }
    }

# --- titres lazy + helper ---
WIZARD_STEP_TITLES = {
    "circuit":        _lazy("Choix du circuit"),
    "pilote":         _lazy("Pilote"),
    "infos_med":      _lazy("Informations médicales"),
    "moto":           _lazy("Moto du pilote"),
    "passager_choix": _lazy("Passager — choix"),
    "passager":       _lazy("Passager"),
    "options":        _lazy("Options du circuit"),
    "assurance":      _lazy("Assurance"),
    "contacts":       _lazy("Contacts d’urgence"),
    "documents":      _lazy("Documents à téléverser"),
    "decharge":       _lazy("Décharge & signature"),
}

from django.utils.translation import gettext as _

def _inject_wizard_titles(view, ctx):
    """Enrichit le contexte avec titres + état (current/completed/clickable) du wizard."""
    current = view.steps.current
    is_edit = bool(getattr(view, "is_edit", False))

    items = list(view.get_form_list().keys())

    try:
        cur_idx = items.index(current)
    except ValueError:
        cur_idx = 0

    steps = []
    for i, name in enumerate(items):
        is_current = (i == cur_idx)
        is_completed = (i < cur_idx)

        # ✅ En édition: toutes les étapes (sauf la courante) sont cliquables
        # ✅ En création: seulement les étapes déjà passées sont cliquables
        is_clickable = (not is_current) and (i <= cur_idx)

        # ✅ URL directe (GET) uniquement utile en édition (navigation pro)
        step_url = ""
        if is_edit:
            try:
                step_url = view.get_step_url(name)
            except Exception:
                step_url = ""

        steps.append({
            "name": name,
            "index": i + 1,
            "title": WIZARD_STEP_TITLES.get(name, name),
            "is_current": is_current,
            "is_completed": is_completed,
            "is_clickable": is_clickable,
            "url": step_url,   # ✅ AJOUT IMPORTANT
        })

    ctx["steps_progress"] = steps
    ctx["current_step_title"] = WIZARD_STEP_TITLES.get(current, current)
    ctx["step_x_of_y"] = _("Étape %(n)s sur %(m)s") % {
        "n": (view.steps.index + 1),
        "m": view.steps.count
    }

    ctx["wizard_mode"] = "edit" if is_edit else "create"
    return ctx

class InscriptionWizardView(NamedUrlSessionWizardView):
    """
    Wizard d'inscription (création)
    """
    form_list = (
        ("circuit",        FormChoixCircuit),
        ("pilote",         FormPilote),
        ("infos_med",      FormInfosMedicales),
        ("moto",           FormMoto),
        ("passager_choix", FormPassagerChoix),
        ("passager",       FormPassager),
        ("options",        FormOptions),
        ("assurance",      FormAssurance),
        ("contacts",       FormContactsUrgence),
        ("documents",      FormDocuments),
        ("decharge",       FormDecharge),
    )
    file_storage = file_storage
    url_name = "inscription_create_step"   # ✅ route de création
    done_step_name = "done"

    condition_dict = {"passager": afficher_passager}

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]


    def post(self, *args, **kwargs):
        goto = self.request.POST.get("wizard_goto_step")
        if goto:
            # Interdire toute tentative d'aller sur une étape > étape courante
            # => on autorise uniquement les retours (<= index actuel)
            all_steps = list(self.get_form_list().keys())
            try:
                goto_idx = all_steps.index(goto)
                cur_idx = all_steps.index(self.steps.current)
            except ValueError:
                goto_idx = cur_idx = 0

            if goto_idx > cur_idx:
                messages.warning(self.request, "Veuillez compléter les étapes précédentes avant d’accéder à celle-ci.")
                # On ignore la demande et on reste sur l'étape en cours
                self.request.POST = self.request.POST.copy()
                self.request.POST.pop("wizard_goto_step", None)

        return super().post(*args, **kwargs)


    # ✅ Mettre le seed ici (self.storage est prêt), PAS dans dispatch()
    def get(self, request, *args, **kwargs):
        data = self.storage.extra_data or {}

        def _clean(v):
            # supprime espaces insécables & espaces autour
            return (str(v).replace("\xa0", "").strip()) if v else ""

        # on accepte seed (pour UUID d’inscription) et personne / seed_personne (pour PK Personne)
        seed_ins = _clean(request.GET.get("seed"))  # UUID d’inscription
        seed_pers = _clean(request.GET.get("personne") or request.GET.get("seed_personne"))

        # stocke seulement s’il n’y a rien encore (évite d’écraser pendant le wizard)
        if seed_ins and not data.get("seed"):
            data["seed"] = seed_ins
        if seed_pers and not data.get("seed_personne"):
            data["seed_personne"] = seed_pers

        self.storage.extra_data = data
        return super().get(request, *args, **kwargs)
    
    page_title = _lazy("Nouvelle inscription")

    def get_context_data(self, form, **kwargs):
        ctx = super().get_context_data(form=form, **kwargs)

        d_pilote = self.get_cleaned_data_for_step("pilote") or {}
        c = _get_selected_circuit_from_wizard(self)

        ctx["circuit_selected"] = c
        ctx["decharge_html"] = _render_decharge_html(
            c,
            pilote_prenom=d_pilote.get("prenom", ""),
            pilote_nom=d_pilote.get("nom", ""),
        )

        ctx["existing_signature_url"] = ""
        ctx["page_title"] = self.page_title
        _inject_wizard_titles(self, ctx)
        return ctx


    def _get_seed_inscription(self):
        """Retourne une Inscription si seed est un UUID valide, sinon None."""
        raw = (self.storage.extra_data or {}).get("seed") or ""
        raw = str(raw).replace("\xa0", "").strip()
        if not raw:
            return None
        try:
            uid = uuid.UUID(raw)
        except Exception:
            return None
        try:
            return (Inscription.objects
                    .select_related("pilote", "passager", "circuit")
                    .prefetch_related("selections_options", "pilote__motos")
                    .get(id_public=uid))
        except Inscription.DoesNotExist:
            return None

    def _get_seed_personne(self):
        """Retourne une Personne si seed_personne (ou seed numérique) est un PK valide, sinon None."""
        data = self.storage.extra_data or {}
        raw = data.get("seed_personne") or data.get("seed") or ""
        raw = str(raw).replace("\xa0", "").strip()
        if not raw or not raw.isdigit():
            return None
        try:
            return Personne.objects.prefetch_related("motos").get(pk=int(raw))
        except Personne.DoesNotExist:
            return None

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        step = step or self.steps.current

        if step == "circuit":
            kwargs["include_archived"] = self.request.user.is_staff  # ⬅️ ICI


        if step == "options":
            data_circuit = self.get_cleaned_data_for_step("circuit") or {}
            circuit = data_circuit.get("circuit")

            choix_pass = self.get_cleaned_data_for_step("passager_choix") or {}
            passager_present = bool(choix_pass.get("avec_passager"))

            kwargs["circuit"] = circuit
            kwargs["passager"] = passager_present

        return kwargs

    # ✅ Il ne doit rester QU’UNE SEULE version de get_form_initial
    # Remplace ta méthode get_form_initial par celle-ci (elle inclut le bloc seed_personne)
    def get_form_initial(self, step):
        initial = super().get_form_initial(step)

        # Pré-sélection via ?circuit=ID
        if step == "circuit":
            cid = self.request.GET.get("circuit")
            if cid:
                try:
                    from .models import Circuit
                    initial["circuit"] = Circuit.objects.get(pk=cid)
                except Exception:
                    pass

        # --- Réinscription via une Inscription (UUID dans ?seed=) ---
        seed_ins = self._get_seed_inscription()
        if seed_ins:
            if step == "pilote":
                p = seed_ins.pilote
                return dict(
                    prenom=p.prenom, nom=p.nom, email=p.email, telephone=p.telephone,
                    date_naissance=p.date_naissance, numero_carte_identite=p.numero_carte_identite, 
                    nationalite=p.nationalite,
                    adresse=p.adresse, code_postal=p.code_postal, localite=p.localite, pays=p.pays
                )
            if step == "moto":
                p = seed_ins.pilote
                m = p.motos.first() if p else None
                if m:
                    return dict(marque=m.marque, modele=m.modele, immatriculation=m.immatriculation)
            if step == "passager_choix":
                return {"avec_passager": bool(seed_ins.passager_id)}
            if step == "passager" and seed_ins.passager_id:
                ps = seed_ins.passager
                return dict(
                    prenom=ps.prenom, nom=ps.nom, email=ps.email,
                    telephone=ps.telephone, date_naissance=ps.date_naissance,
                    nationalite=ps.nationalite,                
                    numero_carte_identite=ps.numero_carte_identite
                )
            if step == "options":
                return {}  # dépend du circuit choisi

        # --- Pré-remplissage via Personne (si seed_personne présent) ---
        seed_personne = self._get_seed_personne()
        if seed_personne:
            if step == "pilote":
                p = seed_personne
                return dict(
                    prenom=p.prenom, nom=p.nom, email=p.email, telephone=p.telephone,
                    date_naissance=p.date_naissance, numero_carte_identite=p.numero_carte_identite,
                    nationalite=p.nationalite,
                    adresse=p.adresse, code_postal=p.code_postal, localite=p.localite, pays=p.pays
                )
            if step == "moto":
                m = seed_personne.motos.first()
                if m:
                    return dict(marque=m.marque, modele=m.modele, immatriculation=m.immatriculation)
            if step in ("passager_choix", "passager", "options"):
                # rien par défaut (dépend des choix)
                return {}

        return initial


    @transaction.atomic
    def done(self, form_list, **kwargs):
        d_circuit  = self.get_cleaned_data_for_step("circuit")
        d_pilote   = self.get_cleaned_data_for_step("pilote")
        d_med      = self.get_cleaned_data_for_step("infos_med") or {}
        d_moto     = self.get_cleaned_data_for_step("moto")
        d_chx      = self.get_cleaned_data_for_step("passager_choix") or {}
        d_passager = self.get_cleaned_data_for_step("passager") if d_chx.get("avec_passager") else None

        # Revalider "options" pour extraire les données
        f_options = self.get_form(step="options", data=self.storage.get_step_data("options"))
        f_options.is_valid()
        selections = f_options.extraire_selection()

        d_assu     = self.get_cleaned_data_for_step("assurance")
        d_contacts = self.get_cleaned_data_for_step("contacts")
        d_docs     = self.get_cleaned_data_for_step("documents")
        d_decharge = self.get_cleaned_data_for_step("decharge")

        # --- NE RIEN FAIRE avec DechargeSignee AVANT la création d'inscription ---

        circuit = d_circuit["circuit"]

        # 1) Pilote
        new_email = _norm_email(d_pilote["email"])
        new_tel   = _norm_tel(d_pilote.get("telephone"))

        pilote, _ = Personne.objects.get_or_create(
            email=new_email,
            telephone=new_tel,
            defaults=dict(
                prenom=d_pilote["prenom"],
                nom=d_pilote["nom"],
                date_naissance=d_pilote.get("date_naissance"),
                numero_carte_identite=d_pilote.get("numero_carte_identite") or "",
                nationalite=d_pilote.get("nationalite") or "",
                adresse=d_pilote.get("adresse") or "",
                code_postal=d_pilote.get("code_postal") or "",
                localite=d_pilote.get("localite") or "",
                pays=d_pilote.get("pays") or "",
            )
        )

        # Si la fiche existante a des champs vides, on les complète
        if _fill_if_blank(pilote, d_pilote, [
            "prenom","nom","date_naissance","numero_carte_identite", "nationalite", "adresse","code_postal","localite","pays"
        ]):
            pilote.save()


        # 1bis) Infos médicales
        if any(d_med.get(k) for k in ["groupe_sanguin","hta","asthme","epilepsie","problemes_peau","vertiges","notes"]):
            InfosMedicales.objects.update_or_create(
                personne=pilote,
                defaults=dict(
                    groupe_sanguin=d_med.get("groupe_sanguin") or "",
                    hta=bool(d_med.get("hta")),
                    asthme=bool(d_med.get("asthme")),
                    epilepsie=bool(d_med.get("epilepsie")),
                    problemes_peau=bool(d_med.get("problemes_peau")),
                    vertiges=bool(d_med.get("vertiges")),
                    notes=d_med.get("notes") or "",
                )
            )

        # 2) Passager (optionnel)
        passager = None
        if d_passager:
            passager_email = d_passager.get("email") or f"passager-{int(timezone.now().timestamp())}@example.com"
            passager, _ = Personne.objects.get_or_create(
                email=passager_email,
                defaults=dict(
                    prenom=d_passager["prenom"],
                    nom=d_passager["nom"],
                    telephone=d_passager.get("telephone") or "",
                    date_naissance=d_passager.get("date_naissance"),

                    numero_carte_identite=d_passager.get("numero_carte_identite") or "",  # ⬅️ AJOUT
                    nationalite=d_passager.get("nationalite") or "",  

                ),
            )
            updates = []
            if d_passager.get("telephone") and passager.telephone != d_passager["telephone"]:
                passager.telephone = d_passager["telephone"]; updates.append("telephone")
            if d_passager.get("date_naissance") and passager.date_naissance != d_passager["date_naissance"]:
                passager.date_naissance = d_passager["date_naissance"]; updates.append("date_naissance")
            if updates:
                passager.save(update_fields=updates)

            if d_passager.get("numero_carte_identite") is not None and passager.numero_carte_identite != d_passager.get("numero_carte_identite"):
                passager.numero_carte_identite = d_passager.get("numero_carte_identite"); updates.append("numero_carte_identite")
            if d_passager.get("nationalite") is not None and passager.nationalite != d_passager.get("nationalite"):
                passager.nationalite = d_passager.get("nationalite"); updates.append("nationalite")
            if updates:
                passager.save(update_fields=updates)


         # Après avoir trouvé `pilote` et `circuit`
        existant = Inscription.objects.filter(circuit=circuit, pilote=pilote).first()
        if existant:
            messages.info(self.request, "Vous étiez déjà inscrit·e à ce circuit. Dossier existant rouvert.")
            return redirect(reverse("inscription_edit_step", kwargs={"id_public": str(existant.id_public), "step": "pilote"}))
       

        # 3) Inscription
        inscription = Inscription.objects.create(
            circuit=circuit, pilote=pilote, passager=passager,
            devise=circuit.devise,
            prix_pilote_unitaire=circuit.prix_pilote_unitaire,
            prix_passager_unitaire=(circuit.prix_passager_unitaire if passager else 0),
        )

        # 4) Moto
        MotoModel.objects.create(
            proprietaire=pilote,
            marque=d_moto["marque"],
            modele=d_moto.get("modele") or "",
            immatriculation=d_moto.get("immatriculation") or "",
        )

        # 5) Options
        for item in selections:
            SelectionOption.objects.create(
                inscription=inscription,
                option=item["option"],
                quantite=item["quantite"],
                prix_unitaire_fige=item["option"].prix_unitaire,
                pour_passager=item["pour_passager"],
            )

        # 6) Assurance
        AssuranceModel.objects.create(
            inscription=inscription,
            type=d_assu["type"],
            compagnie=d_assu.get("compagnie") or "",
            numero_police=d_assu.get("numero_police") or "",
            telephone_urgence=d_assu.get("telephone_urgence") or "",
            valide_du=d_assu.get("valide_du"),
            valide_au=d_assu.get("valide_au"),
        )

        # 7) Contacts d’urgence
        ContactUrgence.objects.create(personne=pilote, nom=d_contacts["nom1"], lien_parente=d_contacts.get("lien1") or "", telephone=d_contacts["tel1"])
        ContactUrgence.objects.create(personne=pilote, nom=d_contacts["nom2"], lien_parente=d_contacts.get("lien2") or "", telephone=d_contacts["tel2"])

        # 8) Documents
        def _save_doc(f, tdoc):
            if not f: return
            Document.objects.create(inscription=inscription, type_document=tdoc, fichier=f, statut="EN_ATTENTE")

        _save_doc(d_docs.get("cni"),                   TypeDocument.CNI)
        _save_doc(d_docs.get("permis"),                TypeDocument.PERMIS_CONDUIRE)
        _save_doc(d_docs.get("carte_grise"),           TypeDocument.CARTE_GRISE)
        _save_doc(d_docs.get("attestation_assurance"), TypeDocument.ATTEST_ASSURANCE)
        _save_doc(d_docs.get("certificat_medical"),    TypeDocument.CERTIF_MEDICAL)

        # 9) Décharge (UN SEUL endroit, après création d'inscription) + sauvegarde signature
        dch = DechargeSignee.objects.create(
            inscription=inscription,
            version_texte="CGV-2025-01",
            nom_signataire=d_decharge["nom_signataire"],
            email_signataire=d_decharge["email_signataire"],
            # otp_4_derniers=d_decharge["otp"][-4:],
            adresse_ip=self.request.META.get("REMOTE_ADDR"),
        )

        sig_data = (d_decharge.get("signature_data") or "").strip()
        m = re.match(r"^data:image/(png|jpeg);base64,(.+)$", sig_data)
        if m:
            ext = m.group(1)
            raw = base64.b64decode(m.group(2))
            name = f"sig-{inscription.id_public}.{ 'png' if ext=='png' else 'jpg' }"
            dch.signature_image.save(name, ContentFile(raw), save=True)

        # 10) Échéancier
        initialiser_plan_paiement_par_defaut(inscription)

        # 11) Notifications e-mail
        notify_inscription_recue(inscription)


        ctx = {"inscription": inscription}
        ctx.update(_build_success_context(inscription))
        return render(self.request, "circuitMoto/inscription/succes.html", ctx)

class InscriptionWizardEditView(NamedUrlSessionWizardView):
    """
    Edition d'une inscription existante via le même wizard.
    - Pré-remplit toutes les étapes (sauf fichiers/OTP).
    - Met à jour au lieu de créer.
    - Gère l'étape passager dynamiquement (apparition/disparition).
    """
    # ✅ IMPORTANT : sinon form_list est vide => AssertionError
    form_list = InscriptionWizardView.form_list
    file_storage = file_storage

    url_name = "inscription_edit_step"
    done_step_name = "done"
    is_edit = True
    inscription = None

    condition_dict = {"passager": afficher_passager}

    def _sync_step_from_url(self, **kwargs):
        """Force le wizard à se caler sur l’étape de l’URL (édition)."""
        step = kwargs.get("step")
        if not step:
            return
        steps = list(self.get_form_list().keys())
        if step in steps:
            self.storage.current_step = step

    def dispatch(self, request, *args, **kwargs):
        raw = kwargs.get("id_public")
        lookup_value = raw if isinstance(getattr(Inscription._meta.get_field("id_public"), "uuid", None), uuid.UUID) else str(raw)

        ins = Inscription.objects.filter(id_public=lookup_value).first()
        if not ins:
            messages.error(request, "Référence introuvable. Réessayez ci-dessous.")
            return redirect("inscription_lookup")

        self.inscription = ins
        if self.inscription.est_verrouillee():
            raise PermissionDenied("Cette inscription est verrouillée et ne peut plus être modifiée.")

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        # ✅ storage prêt ici
        self._sync_step_from_url(**kwargs)
        return super().get(request, *args, **kwargs)

    def post(self, *args, **kwargs):
        self._sync_step_from_url(**kwargs)

        action = self.request.POST.get("wizard_action")
        if action != "save":
            return super().post(*args, **kwargs)

        # ✅ Valider uniquement l'étape courante
        step = self.steps.current
        form = self.get_form(step=step, data=self.request.POST, files=self.request.FILES)

        if not form.is_valid():
            return self.render(form)

        # ✅ On stocke cette étape dans la storage (pour que get_cleaned_data_for_step fonctionne)
        self.storage.set_step_data(step, self.process_step(form))
        self.storage.set_step_files(step, self.process_step_files(form))

        # ✅ Sauvegarde globale avec fallback DB pour étapes non visitées
        self._save_with_fallback()

        messages.success(self.request, "Modifications enregistrées.")
        return redirect(self.get_step_url(step))

    
    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]
    

    def get_step_url(self, step):
        return reverse(self.url_name, kwargs={
            "id_public": str(self.inscription.id_public),
            "step": step,
        })    
    

    def get_context_data(self, form, **kwargs):
        ctx = super().get_context_data(form=form, **kwargs)

        d_pilote = self.get_cleaned_data_for_step("pilote") or {}
        c = _get_selected_circuit_from_wizard(self) or self.inscription.circuit

        prenom = d_pilote.get("prenom") or self.inscription.pilote.prenom
        nom    = d_pilote.get("nom")    or self.inscription.pilote.nom

        ctx["circuit_selected"] = c
        ctx["decharge_html"] = _render_decharge_html(c, pilote_prenom=prenom, pilote_nom=nom)

        sig_url = ""
        if hasattr(self.inscription, "decharge") and getattr(self.inscription.decharge, "signature_image", None):
            if self.inscription.decharge.signature_image:
                sig_url = self.inscription.decharge.signature_image.url
        ctx["existing_signature_url"] = sig_url

        # ✅ AJOUTS
        ctx["page_title"] = getattr(self, "page_title", _lazy("Inscription"))
        _inject_wizard_titles(self, ctx)
        return ctx   # ✅ inject steps_progress + current_step_title + step_x_of_y + wizard_mode

    # Affiche/masque l'étape "passager"
    # def get_form_list(self):
    #     form_list = super().get_form_list()  # OrderedDict
    #     choix = self.get_cleaned_data_for_step("passager_choix")
    #     if choix is None:
    #         # 1er affichage: calqué sur l'inscription existante
    #         if not self.inscription.passager_id:
    #             form_list.pop("passager", None)
    #     else:
    #         if not bool(choix.get("avec_passager")):
    #             form_list.pop("passager", None)
    #     return form_list


    # kwargs dynamiques (uniquement pour "options")
    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        step = step or self.steps.current

        # --- Etape "circuit"
        if step == "circuit":
            kwargs["include_archived"] = self.request.user.is_staff
            kwargs["force_include_circuit_id"] = self.inscription.circuit_id  # ⬅️ ajout clé

        # --- Etape "options" (inchangé)
        if step == "options":
            data_circuit = self.get_cleaned_data_for_step("circuit")
            circuit = (data_circuit or {}).get("circuit") or self.inscription.circuit
            choix_pass = self.get_cleaned_data_for_step("passager_choix")
            passager_present = (bool(choix_pass.get("avec_passager"))
                                if choix_pass is not None else bool(self.inscription.passager_id))
            kwargs["circuit"] = circuit
            kwargs["passager"] = passager_present

        # --- Etape "documents" (inchangé)
        elif step == "documents":
            kwargs["is_edit"] = True
            docs = {d.type_document: d for d in self.inscription.documents.all()}
            def meta(d):
                if not d or not d.fichier:
                    return None
                return {
                    "url": d.fichier.url,
                    "name": os.path.basename(d.fichier.name),
                    "status": d.get_statut_display(),
                }
            kwargs["existing_docs"] = {
                "cni": meta(docs.get(TypeDocument.CNI)),
                "permis": meta(docs.get(TypeDocument.PERMIS_CONDUIRE)),
                "carte_grise": meta(docs.get(TypeDocument.CARTE_GRISE)),
                "attestation_assurance": meta(docs.get(TypeDocument.ATTEST_ASSURANCE)),
                "certificat_medical": meta(docs.get(TypeDocument.CERTIF_MEDICAL)),
            }
        return kwargs

    # initial des formulaires (pré-remplissage)
    def get_form_initial(self, step):
        ins = self.inscription


        if step == "infos_med":  # ⬅️ AJOUT
            im = getattr(ins.pilote, "infos_medicales", None)
            if im:
                return dict(
                    groupe_sanguin=im.groupe_sanguin or "",
                    hta=im.hta, asthme=im.asthme, epilepsie=im.epilepsie,
                    problemes_peau=im.problemes_peau, vertiges=im.vertiges,
                    notes=im.notes,
                )
            return {}

        if step == "circuit":
            return {"circuit": ins.circuit}
        if step == "pilote":
            p = ins.pilote
            return dict(
                prenom=p.prenom, nom=p.nom, email=p.email, telephone=p.telephone,
                date_naissance=p.date_naissance, numero_carte_identite=p.numero_carte_identite,
                nationalite=p.nationalite,
                adresse=p.adresse, code_postal=p.code_postal, localite=p.localite, pays=p.pays
            )
        if step == "moto":
            m = ins.pilote.motos.first()
            if m:
                return dict(marque=m.marque, modele=m.modele, immatriculation=m.immatriculation)
            return {}
        if step == "passager_choix":
            return {"avec_passager": bool(ins.passager_id)}
        if step == "passager" and ins.passager_id:
            ps = ins.passager
            return dict(prenom=ps.prenom, nom=ps.nom, email=ps.email,
                        telephone=ps.telephone, date_naissance=ps.date_naissance,
                        nationalite=ps.nationalite,                  
                        numero_carte_identite=ps.numero_carte_identite )
        if step == "assurance" and hasattr(ins, "assurance"):
            a = ins.assurance
            return dict(type=a.type, compagnie=a.compagnie, numero_police=a.numero_police,
                        telephone_urgence=a.telephone_urgence,
                        valide_du=a.valide_du, valide_au=a.valide_au)
        if step == "contacts":
            cs = list(ins.pilote.contacts_urgence.all()[:2])
            data = {}
            if len(cs) > 0:
                data.update(dict(nom1=cs[0].nom, lien1=cs[0].lien_parente, tel1=cs[0].telephone))
            if len(cs) > 1:
                data.update(dict(nom2=cs[1].nom, lien2=cs[1].lien_parente, tel2=cs[1].telephone))
            return data
        if step == "documents":
            # On ne pré-remplit pas les FileField (sécurité/navigateur)
            return {}
        if step == "decharge":
            # On pré-remplit uniquement nom/email; OTP & consentement à ressaisir
            nom = ins.decharge.nom_signataire if hasattr(ins, "decharge") else (ins.pilote.nom_complet)
            email = ins.decharge.email_signataire if hasattr(ins, "decharge") else ins.pilote.email
            return {"nom_signataire": nom, "email_signataire": email}
        if step == "options":
            # Initial dynamique depuis selections_options
            initial = {}
            for sel in ins.selections_options.select_related("option").all():
                opt = sel.option
                if opt.facture_par_personne:
                    suffixe = "passager" if sel.pour_passager else "pilote"
                    fname = f"opt_{opt.pk}_{suffixe}"
                else:
                    fname = f"opt_{opt.pk}"
                if opt.quantite_variable:
                    initial[fname] = sel.quantite
                else:
                    initial[fname] = bool(sel.quantite > 0)
            return initial
        return {}

    def _save_with_fallback(self):
        """
        Applique les modifications en utilisant :
        - les données du wizard si présentes (storage)
        - sinon les valeurs actuelles en base (self.inscription)
        """
        ins = self.inscription

        # helper: data wizard ou fallback DB
        def cd(step):
            return self.get_cleaned_data_for_step(step)

        def fallback_pilote(p):
            return dict(
                prenom=p.prenom, nom=p.nom, email=p.email, telephone=p.telephone,
                date_naissance=p.date_naissance, numero_carte_identite=p.numero_carte_identite,
                nationalite=p.nationalite, adresse=p.adresse, code_postal=p.code_postal,
                localite=p.localite, pays=p.pays
            )

        def fallback_passager(ps):
            return dict(
                prenom=ps.prenom, nom=ps.nom, email=ps.email,
                telephone=ps.telephone, date_naissance=ps.date_naissance,
                numero_carte_identite=ps.numero_carte_identite,
                nationalite=ps.nationalite
            )

        # ---- récupérer données (wizard ou DB)
        d_circuit = cd("circuit") or {"circuit": ins.circuit}
        d_pilote  = cd("pilote") or fallback_pilote(ins.pilote)

        # infos médicales
        d_med = cd("infos_med")
        if d_med is None:
            im = getattr(ins.pilote, "infos_medicales", None)
            d_med = dict(
                groupe_sanguin=getattr(im, "groupe_sanguin", "") or "",
                hta=bool(getattr(im, "hta", False)),
                asthme=bool(getattr(im, "asthme", False)),
                epilepsie=bool(getattr(im, "epilepsie", False)),
                problemes_peau=bool(getattr(im, "problemes_peau", False)),
                vertiges=bool(getattr(im, "vertiges", False)),
                notes=getattr(im, "notes", "") or "",
            )

        # moto
        d_moto = cd("moto")
        if d_moto is None:
            m = ins.pilote.motos.first()
            d_moto = dict(
                marque=getattr(m, "marque", "") or "",
                modele=getattr(m, "modele", "") or "",
                immatriculation=getattr(m, "immatriculation", "") or "",
            )

        d_chx = cd("passager_choix")
        if d_chx is None:
            d_chx = {"avec_passager": bool(ins.passager_id)}

        d_passager = cd("passager") if d_chx.get("avec_passager") else None
        if d_passager is None and d_chx.get("avec_passager") and ins.passager_id:
            d_passager = fallback_passager(ins.passager)

        d_assu = cd("assurance")
        if d_assu is None:
            a = getattr(ins, "assurance", None)
            d_assu = dict(
                type=getattr(a, "type", "") or "",
                compagnie=getattr(a, "compagnie", "") or "",
                numero_police=getattr(a, "numero_police", "") or "",
                telephone_urgence=getattr(a, "telephone_urgence", "") or "",
                valide_du=getattr(a, "valide_du", None),
                valide_au=getattr(a, "valide_au", None),
            )

        d_contacts = cd("contacts")
        if d_contacts is None:
            cs = list(ins.pilote.contacts_urgence.all()[:2])
            d_contacts = {
                "nom1": cs[0].nom if len(cs) > 0 else "",
                "lien1": cs[0].lien_parente if len(cs) > 0 else "",
                "tel1": cs[0].telephone if len(cs) > 0 else "",
                "nom2": cs[1].nom if len(cs) > 1 else "",
                "lien2": cs[1].lien_parente if len(cs) > 1 else "",
                "tel2": cs[1].telephone if len(cs) > 1 else "",
            }

        d_docs = cd("documents") or {}          # files seulement si l'étape a été visitée
        d_decharge = cd("decharge") or {
            "nom_signataire": getattr(getattr(ins, "decharge", None), "nom_signataire", ins.pilote.nom_complet),
            "email_signataire": getattr(getattr(ins, "decharge", None), "email_signataire", ins.pilote.email),
            "signature_data": "",
        }

        # options : si pas visité -> reprendre celles en base
        selections = None
        if self.storage.get_step_data("options"):
            f_options = self.get_form(step="options", data=self.storage.get_step_data("options"))
            f_options.is_valid()
            selections = f_options.extraire_selection()
        else:
            selections = [
                {
                    "option": sel.option,
                    "quantite": sel.quantite,
                    "pour_passager": sel.pour_passager,
                }
                for sel in ins.selections_options.select_related("option").all()
            ]

        # ✅ Maintenant on applique exactement ta logique de done() (édition),
        # mais en utilisant ces variables d_* déjà fiables (wizard ou DB).
        # Le plus simple : appelle une fonction interne qui reprend ton code done() en remplaçant les d_*

        result = self._apply_edit_update(
            ins=ins,
            d_circuit=d_circuit,
            d_pilote=d_pilote,
            d_med=d_med,
            d_moto=d_moto,
            d_chx=d_chx,
            d_passager=d_passager,
            selections=selections,
            d_assu=d_assu,
            d_contacts=d_contacts,
            d_docs=d_docs,
            d_decharge=d_decharge,
        )

        # si conflit -> redirect()
        if isinstance(result, HttpResponseBase):
            return result

        # sinon c'est l'inscription mise à jour
        self.inscription = result or ins
        return self.inscription

    # Dans InscriptionWizardEditView (views.py)
    # Ajoute ces imports si pas déjà présents en haut du fichier :
    # from django.utils import timezone
    # from django.contrib import messages
    # from django.db import transaction
    # from django.core.files.base import ContentFile
    # import base64, re, os, uuid

    # 2810cd3c-cc92-4fa1-8ede-33c5196fac16

    @transaction.atomic
    def _apply_edit_update(
        self,
        ins,
        d_circuit,
        d_pilote,
        d_med,
        d_moto,
        d_chx,
        d_passager,
        selections,
        d_assu,
        d_contacts,
        d_docs,
        d_decharge,
    ):
        """
        Applique toutes les MAJ d'une inscription existante (édition),
        en partant de données déjà "fiables" (wizard si présentes, sinon fallback DB).

        IMPORTANT : cette méthode ne rend pas de template. Elle sauvegarde et retourne l'inscription.
        Elle peut retourner une HttpResponseRedirect si conflit (doublon circuit+pilote).
        """

        # 1) Circuit
        nouveau_circuit = d_circuit["circuit"]

        # Interdit côté public si non publié
        if (not self.request.user.is_staff) and getattr(nouveau_circuit, "statut", None) != "PUBLIE":
            raise PermissionDenied("Ce circuit n'est plus ouvert aux inscriptions.")

        # On travaille sur l'objet courant en RAM
        ins.circuit = nouveau_circuit
        ins.devise = nouveau_circuit.devise

        # 2) MAJ pilote — et détection de conflit (circuit + pilote)
        p = ins.pilote
        new_email = _norm_email(d_pilote["email"])
        new_tel = _norm_tel(d_pilote.get("telephone"))

        other = (
            Personne.objects.exclude(pk=p.pk)
            .filter(email=new_email, telephone=new_tel)
            .first()
        )

        # Candidat pilote après édition (soit 'other' si doublon fiche, soit 'p')
        pilote_candidat = other or p

        # ⚠️ Conflit d’unicité ? (une AUTRE inscription existe déjà avec ce couple)
        conflit = (
            Inscription.objects.filter(circuit=nouveau_circuit, pilote=pilote_candidat)
            .exclude(pk=ins.pk)
            .first()
        )

        if conflit:
            messages.warning(
                self.request,
                "Ce pilote est déjà inscrit sur ce circuit. "
                "Je vous redirige vers son dossier pour éviter un doublon."
            )
            return redirect(reverse(self.url_name, kwargs={
                "id_public": str(conflit.id_public),
                "step": "pilote",
            }))

        # Pas de conflit : on met à jour réellement le pilote
        if other:
            # Rattache l’inscription à la fiche existante et complète ses champs vides
            if _fill_if_blank(other, d_pilote, [
                "prenom", "nom", "date_naissance", "numero_carte_identite",
                "nationalite", "adresse", "code_postal", "localite", "pays"
            ]):
                other.save()
            ins.pilote = other
            p = other
        else:
            # Mise à jour des champs de la fiche actuelle
            p.email = new_email
            p.telephone = new_tel
            for champ in [
                "prenom", "nom", "date_naissance", "numero_carte_identite",
                "nationalite", "adresse", "code_postal", "localite", "pays"
            ]:
                val = d_pilote.get(champ)
                if val is not None:
                    setattr(p, champ, val)
            p.save()

        # 2bis) Infos médicales
        # Même logique que création : update_or_create uniquement si des champs existent
        if d_med is None:
            d_med = {}
        if any(d_med.get(k) for k in ["groupe_sanguin", "hta", "asthme", "epilepsie", "problemes_peau", "vertiges", "notes"]):
            InfosMedicales.objects.update_or_create(
                personne=p,
                defaults=dict(
                    groupe_sanguin=d_med.get("groupe_sanguin") or "",
                    hta=bool(d_med.get("hta")),
                    asthme=bool(d_med.get("asthme")),
                    epilepsie=bool(d_med.get("epilepsie")),
                    problemes_peau=bool(d_med.get("problemes_peau")),
                    vertiges=bool(d_med.get("vertiges")),
                    notes=d_med.get("notes") or "",
                )
            )

        # 3) MAJ passager
        if d_passager:
            if ins.passager_id:
                ps = ins.passager
                ps.prenom = d_passager["prenom"]
                ps.nom = d_passager["nom"]
                ps.email = d_passager.get("email") or ps.email
                ps.telephone = d_passager.get("telephone") or ps.telephone
                ps.date_naissance = d_passager.get("date_naissance")

                # champs ajoutés
                ps.numero_carte_identite = d_passager.get("numero_carte_identite") or ps.numero_carte_identite
                ps.nationalite = d_passager.get("nationalite") or ps.nationalite

                ps.save()
            else:
                email_ps = d_passager.get("email") or f"passager-{int(timezone.now().timestamp())}@example.com"
                ps, _ = Personne.objects.get_or_create(
                    email=email_ps,
                    defaults=dict(
                        prenom=d_passager["prenom"],
                        nom=d_passager["nom"],
                        telephone=d_passager.get("telephone") or "",
                        date_naissance=d_passager.get("date_naissance"),
                        numero_carte_identite=d_passager.get("numero_carte_identite") or "",
                        nationalite=d_passager.get("nationalite") or "",
                    )
                )
                ins.passager = ps
                ins.prix_passager_unitaire = nouveau_circuit.prix_passager_unitaire
        else:
            ins.passager = None
            ins.prix_passager_unitaire = 0

        # Snapshots de prix après connaissance du passager
        ins.prix_pilote_unitaire = nouveau_circuit.prix_pilote_unitaire
        ins.prix_passager_unitaire = (nouveau_circuit.prix_passager_unitaire if ins.passager_id else 0)

        # 4) MAJ moto (du pilote)
        m = p.motos.first()
        if m:
            m.marque = d_moto["marque"]
            m.modele = d_moto.get("modele") or ""
            m.immatriculation = d_moto.get("immatriculation") or ""
            m.save()
        else:
            MotoModel.objects.create(
                proprietaire=p,
                marque=d_moto["marque"],
                modele=d_moto.get("modele") or "",
                immatriculation=d_moto.get("immatriculation") or "",
            )

        ins.save()

        # 5) MAJ options : on remplace l'existant
        ins.selections_options.all().delete()

        # selections est une liste d'objets {option, quantite, pour_passager}
        for item in selections or []:
            opt = item["option"]
            qty = int(item.get("quantite") or 0)

            SelectionOption.objects.create(
                inscription=ins,
                option=opt,
                quantite=qty,
                prix_unitaire_fige=opt.prix_unitaire,
                pour_passager=bool(item.get("pour_passager")),
            )

        # 6) MAJ assurance
        if hasattr(ins, "assurance"):
            a = ins.assurance
            a.type = d_assu["type"]
            a.compagnie = d_assu.get("compagnie") or ""
            a.numero_police = d_assu.get("numero_police") or ""
            a.telephone_urgence = d_assu.get("telephone_urgence") or ""
            a.valide_du = d_assu.get("valide_du")
            a.valide_au = d_assu.get("valide_au")
            a.save()
        else:
            AssuranceModel.objects.create(
                inscription=ins,
                type=d_assu["type"],
                compagnie=d_assu.get("compagnie") or "",
                numero_police=d_assu.get("numero_police") or "",
                telephone_urgence=d_assu.get("telephone_urgence") or "",
                valide_du=d_assu.get("valide_du"),
                valide_au=d_assu.get("valide_au"),
            )

        # 7) MAJ contacts (simple : on remplace les 2)
        ins.pilote.contacts_urgence.all().delete()
        if d_contacts:
            # on garde ta logique : 2 contacts attendus
            ContactUrgence.objects.create(
                personne=p,
                nom=d_contacts["nom1"],
                lien_parente=d_contacts.get("lien1") or "",
                telephone=d_contacts["tel1"]
            )
            ContactUrgence.objects.create(
                personne=p,
                nom=d_contacts["nom2"],
                lien_parente=d_contacts.get("lien2") or "",
                telephone=d_contacts["tel2"]
            )

        # 8) MAJ documents (remplace le fichier si un nouveau est fourni)
        def _maj_doc(fichier, type_doc):
            if not fichier:
                return
            try:
                d = Document.objects.get(inscription=ins, type_document=type_doc)
                d.fichier = fichier
                d.statut = "EN_ATTENTE"   # ✅ chez toi c'est un CharField
                d.verifie_par = None
                d.verifie_le = None
                d.note = ""
                d.save()
            except Document.DoesNotExist:
                Document.objects.create(
                    inscription=ins,
                    type_document=type_doc,
                    fichier=fichier,
                    statut="EN_ATTENTE"     # ✅ chez toi c'est un CharField
                )

        if d_docs:
            _maj_doc(d_docs.get("cni"), TypeDocument.CNI)
            _maj_doc(d_docs.get("permis"), TypeDocument.PERMIS_CONDUIRE)
            _maj_doc(d_docs.get("carte_grise"), TypeDocument.CARTE_GRISE)
            _maj_doc(d_docs.get("attestation_assurance"), TypeDocument.ATTEST_ASSURANCE)
            _maj_doc(d_docs.get("certificat_medical"), TypeDocument.CERTIF_MEDICAL)

        # 9) MAJ décharge (ré-acceptation rapide)
        sig_data = (d_decharge.get("signature_data") or "").strip()

        if hasattr(ins, "decharge"):
            dch = ins.decharge
            dch.nom_signataire = d_decharge["nom_signataire"]
            dch.email_signataire = d_decharge["email_signataire"]
            dch.signee_le = timezone.now()
            dch.adresse_ip = self.request.META.get("REMOTE_ADDR")

            # si une nouvelle signature est transmise, on remplace
            m = re.match(r"^data:image/(png|jpeg);base64,(.+)$", sig_data)
            if m:
                ext = m.group(1)
                raw = base64.b64decode(m.group(2))
                name = f"sig-{ins.id_public}.{'png' if ext == 'png' else 'jpg'}"
                dch.signature_image.save(name, ContentFile(raw), save=False)

            dch.save()
        else:
            dch = DechargeSignee.objects.create(
                inscription=ins,
                version_texte="CGV-2025-01",
                nom_signataire=d_decharge["nom_signataire"],
                email_signataire=d_decharge["email_signataire"],
                adresse_ip=self.request.META.get("REMOTE_ADDR"),
            )
            m = re.match(r"^data:image/(png|jpeg);base64,(.+)$", sig_data)
            if m:
                ext = m.group(1)
                raw = base64.b64decode(m.group(2))
                name = f"sig-{ins.id_public}.{'png' if ext == 'png' else 'jpg'}"
                dch.signature_image.save(name, ContentFile(raw), save=True)

        # 10) Recalcule l’échéancier complet sans perdre les encaissements existants
        recalculer_plan_paiement_en_conservant_encaissements(ins)

        return ins
    
    @transaction.atomic
    def done(self, form_list, **kwargs):
        """
        Étape finale /done/ en mode édition.
        On applique la sauvegarde globale (wizard + fallback DB),
        puis on affiche la page succès (récap).
        """
        result = self._save_with_fallback()

        # si _apply_edit_update a renvoyé un redirect (conflit doublon)
        if isinstance(result, HttpResponseBase):
            return result

        messages.success(self.request, "Modifications enregistrées avec succès.")

        ctx = {"inscription": self.inscription}
        ctx.update(_build_success_context(self.inscription))
        return render(self.request, "circuitMoto/inscription/succes.html", ctx)

# === Données programmes (peuvent venir d'une DB plus tard) ===
PROGRAMMES = {
    2026: {
        "intro": (
            "Sauf pour les pays hors Europe, nos circuits se font avec votre moto. "
            "Nous pouvons toutefois, si vous le souhaitez, trouver une moto de location au départ de Belgique "
            "ou au départ de la destination principale. Les prix et dates communiqués peuvent encore légèrement "
            "évoluer (ex : traversées). Si un circuit rencontre peu de succès et que vous avez marqué un intérêt "
            "ou payé un acompte, nous vous préviendrons rapidement, proposerons une alternative ou rembourserons l’acompte."
        ),
        "items": [
            # --- 1er semestre ---
            {
                "title": "Raid Maroc : route ou piste",
                "dates": "15/3 → 1/4 (17 jours)",
                "price": "2 350 €",
                "code": "MAROC-RAID-2026-01",
            },
            {
                "title": "Raid GS / Ténéré (Maroc) – location",
                "dates": "20/3 → 23/3 (10 jours)",
                "price": "1 950 €",
                "links": [
                    {"label": "Détails", "href": "https://pulsionhorizon.com/raidgsmaroc"},
                    {"label": "PDF", "href": "https://static1.squarespace.com/static/55ba69cae4b00bb94e12e391/t/67b704b16b45d8310ea32f73/1740047543203/Programme+Maroc+en+GS+Tour+Dec+25+-+Avril+26.pdf"},
                ],
                "code": "MAROC-GS-2026-01",
            },
            {
                "title": "Raid Maroc en Enfield (location)",
                "dates": "31/3 → 12/4 (13 jours)",
                "price": "2 290 €",
                "code": "MAROC-ENFIELD-2026-01",
            },
            {
                "title": "Luxembourg / Eifel",
                "dates": "24/4 → 25/4 (2 jours)",
                "price": "119 €",
                "links": [{"label":"Infos","href":"https://pulsionhorizon.com/luxembourg-eifel"}],
                "code": "LUX-EIFEL-2026-01",
            },
            {
                "title": "Forêt Noire",
                "dates": "28/4 → 2/5 (5 jours)",
                "price": "à déterminer",
                "code": "FORET-NOIRE-2026-01",
            },
            {
                "title": "Jura",
                "dates": "2/5 → 7/5 (5 ou 6 jours)",
                "price": "490 €",
                "links": [
                    {"label":"Infos","href":"https://pulsionhorizon.com/le-jura"},
                    {"label":"Playlist","href":"https://www.youtube.com/watch?v=bCrqoGDP7_4&list=PLdMDxuSlIsrt2-XsbWV3KImbHalHc8vFw&pp=gAQBiAQB"},
                ],
                "code": "JURA-2026-01",
            },
            {
                "title": "Le Morvan",
                "dates": "2/5 → 7/5 (5 ou 6 jours)",
                "price": "490 €",
                "links": [{"label":"Infos","href":"https://pulsionhorizon.com/le-morvan"}],
                "code": "MORVAN-2026-01",
            },
            {
                "title": "USA en Harley",
                "dates": "15/4 → 26/4 ou → 1/5 (12 ou 17 jours)",
                "price": "4 490 € (12 j) · 6 900 € (17 j)",
                "links": [
                    {"label":"Infos","href":"https://pulsionhorizon.com/usa"},
                    {"label":"Playlist 2024","href":"https://youtube.com/playlist?list=PLdMDxuSlIsrvRreSOAEgq9vWwwoJUzh-h&si=s6jcMq4lud0D-V6c"},
                ],
                "code": "USA-HARLEY-2026-01",
            },
            {
                "title": "Sardaigne",
                "dates": "7/5 ou 19/5 (11 ou 13 jours)",
                "price": "1 230 €",
                "links": [
                    {"label":"Infos","href":"https://pulsionhorizon.com/lasardaigne"},
                    {"label":"Playlist 2023","href":"https://www.youtube.com/playlist?list=PLdMDxuSlIsrsX4-o5ZCZLDGm24-qjv4l2"},
                    {"label":"Reportage 2022 — Ép. 1","href":"https://youtu.be/3Bkc--8wibE"},
                    {"label":"Ép. 2","href":"https://youtu.be/QS_6jUSte2Y"},
                ],
                "code": "SARDAIGNE-2026-01",
            },
            {
                "title": "Pyrénées",
                "dates": "8/5 ou 15/5 (9 ou 10 jours)",
                "price": "1 290 €",
                "links": [{"label":"Infos","href":"https://pulsionhorizon.com/pyrenees"}],
                "code": "PYRENEES-2026-01",
            },
            {
                "title": "Corse I",
                "dates": "18/5 ou 19/5 → 29/5 ou 30/5 (11 ou 13 jours)",
                "price": "1 035 €",
                "links": [
                    {"label":"Infos","href":"https://pulsionhorizon.com/la-corse"},
                    {"label":"Playlist 2023","href":"https://youtube.com/playlist?list=PLdMDxuSlIsrtB1Mu0jR47SpxJgbNTbZx3"},
                    {"label":"Playlist 2025","href":"https://youtube.com/playlist?list=PLdMDxuSlIsrssgrFywiJlSqS1nxuB8B3o"},
                ],
                "code": "CORSE-2026-01",
            },
            {
                "title": "Lorraine & Vosges",
                "dates": "16/5 → 18/5 (3 jours)",
                "price": "230 €",
                "code": "LORRAINE-VOSGES-2026-01",
            },
            {
                "title": "Toscane – Cinque Terre – Lac de Garde",
                "dates": "27/5 → 5/6 (8 ou 10 jours)",
                "price": "1 190 €",
                "links": [{"label":"Infos","href":"https://pulsionhorizon.com/toscane"}],
                "code": "TOSCANE-CINQUE-GARDE-2026-01",
            },
            {
                "title": "Normandie – Bretagne",
                "dates": "6/6 → 10/6 (5 jours)",
                "price": "à déterminer",
                "code": "NORMANDIE-BRETAGNE-2026-01",
            },
            {
                "title": "Dolomites",
                "dates": "11/6 → 19/6 (8 ou 9 jours)",
                "price": "1 190 €",
                "links": [
                    {"label":"Infos","href":"https://pulsionhorizon.com/dolomites"},
                    {"label":"Playlist","href":"https://www.youtube.com/watch?v=-2h6ZFdGNlE&list=PLdMDxuSlIsrsVqcK_Q3sNJ3l3QWh8ggTU&pp=gAQBiAQB"},
                    {"label":"Playlist 2025","href":"https://youtube.com/playlist?list=PLdMDxuSlIsrt5ptnzvbHiU_RWroUsP2F5&si=8S45kDVqxAdnVxgx"},
                ],
                "code": "DOLOMITES-2026-01",
            },
            {
                "title": "Alsace",
                "dates": "17/6 → 21/6 (3, 4 ou 5 jours)",
                "price": "340 €",
                "links": [{"label":"Infos","href":"https://pulsionhorizon.com/alsace"}],
                "code": "ALSACE-2026-01",
            },
            {
                "title": "Écosse",
                "dates": "21/6 → 29/6 (9 jours)",
                "price": "1 490 €",
                "links": [
                    {"label":"Infos","href":"https://pulsionhorizon.com/ecosses"},
                    {"label":"Playlist","href":"https://www.youtube.com/watch?v=Q3J-oxwZjMk&list=PLdMDxuSlIsrugpwGQFGlVka2MfxpM1fmu&pp=gAQBiAQB"},
                ],
                "code": "ECOSSE-2026-01",
            },
            {
                "title": "Corse II",
                "dates": "29/6 ou 30/6 → 10/7 ou 11/7 (11 ou 13 jours)",
                "price": "1 035 €",
                "links": [
                    {"label":"Infos","href":"https://pulsionhorizon.com/la-corse"},
                    {"label":"Playlist 2023","href":"https://youtube.com/playlist?list=PLdMDxuSlIsrtB1Mu0jR47SpxJgbNTbZx3&si=NXFVeonGvJpRcXwz"},
                    {"label":"Playlist 2025","href":"https://youtube.com/playlist?list=PLdMDxuSlIsrssgrFywiJlSqS1nxuB8B3o&si=Lt-ydeuC5cL33jze"},
                ],
                "code": "CORSE-2026-02",
            },

            # --- 2e semestre ---
            {"divider": "Deuxième semestre"},

            {
                "title": "Corse III",
                "dates": "26/8 ou 27/8 → 6/9 ou 7/9 (11 ou 13 jours)",
                "price": "1 035 €",
                "links": [
                    {"label":"Infos","href":"https://pulsionhorizon.com/la-corse"},
                    {"label":"Playlist 2023","href":"https://youtube.com/playlist?list=PLdMDxuSlIsrtB1Mu0jR47SpxJgbNTbZx3&si=NXFVeonGvJpRcXwz"},
                    {"label":"Playlist 2025","href":"https://youtube.com/playlist?list=PLdMDxuSlIsrssgrFywiJlSqS1nxuB8B3o&si=Lt-ydeuC5cL33jze"},
                ],
                "code": "CORSE-2026-03",
            },
            {
                "title": "Alpes du Sud",
                "dates": "27/8 → 4/9 (9 jours)",
                "price": "1 190 €",
                "code": "ALPES-SUD-2026-01",
            },
            {
                "title": "Croatie",
                "dates": "5/9 → 18/9 (12 ou 14 jours)",
                "price": "1 230 €",
                "links": [
                    {"label":"Infos","href":"https://pulsionhorizon.com/la-croatie"},
                    {"label":"Playlist 2024","href":"https://youtube.com/playlist?list=PL52AtAN9nw2N3SMrc75YGh5vEo7u6SCpU&si=7ZgPdwM2fR9TtC8n"},
                    {"label":"Playlist 2023","href":"https://www.youtube.com/playlist?list=PLdMDxuSlIsrvC28U-9T14AnaJLn5so2UR"},
                ],
                "code": "CROATIE-2026-01",
            },
            {
                "title": "Dolomites II",
                "dates": "5/9 → 13/9 (8 ou 9 jours)",
                "price": "1 190 €",
                "links": [{"label":"Infos","href":"https://pulsionhorizon.com/dolomites"}],
                "code": "DOLOMITES-2026-02",
            },
            {
                "title": "Alsace II",
                "dates": "11/9 ou 15/9 (3 ou 5 jours)",
                "price": "340 €",
                "links": [{"label":"Infos","href":"https://pulsionhorizon.com/alsace"}],
                "code": "ALSACE-2026-02",
            },
            {
                "title": "Corse IV",
                "dates": "16/9 ou 17/9 → 27/9 ou 28/9 (11 ou 13 jours)",
                "price": "1 035 €",
                "links": [
                    {"label":"Infos","href":"https://pulsionhorizon.com/la-corse"},
                    {"label":"Playlist 2023","href":"https://youtube.com/playlist?list=PLdMDxuSlIsrtB1Mu0jR47SpxJgbNTbZx3&si=NXFVeonGvJpRcXwz"},
                    {"label":"Playlist 2025","href":"https://youtube.com/playlist?list=PLdMDxuSlIsrssgrFywiJlSqS1nxuB8B3o&si=Lt-ydeuC5cL33jze"},
                ],
                "code": "CORSE-2026-04",
            },
            {
                "title": "Raid Maroc : route ou piste",
                "dates": "2/10 → 18/10 (17 jours)",
                "price": "2 350 €",
                "code": "MAROC-RAID-2026-02",
            },
            {
                "title": "Raid GS / Ténéré (Maroc) – location",
                "dates": "6/10 → 19/10 (10 jours)",
                "price": "1 950 €",
                "links": [
                    {"label":"Détails","href":"https://pulsionhorizon.com/raidgsmaroc"},
                    {"label":"PDF","href":"https://static1.squarespace.com/static/55ba69cae4b00bb94e12e391/t/67b704b16b45d8310ea32f73/1740047543203/Programme+Maroc+en+GS+Tour+Dec+25+-+Avril+26.pdf"},
                ],
                "code": "MAROC-GS-2026-02",
            },
            {
                "title": "Raid Bruxelles → Dakar (100% route ou mixte)",
                "dates": "2/10 → 24/10 (23 jours)",
                "price": "4 750 €",
                "links": [
                    {"label":"Infos","href":"https://pulsionhorizon.com/raid-bruxelles-dakar"},
                    {"label":"Playlist 2023","href":"https://www.youtube.com/playlist?list=PLdMDxuSlIsrvZ5QeRNFsaW5II4qNcBga8"},
                ],
                "code": "BRUXELLES-DAKAR-2026-01",
            },
            {
                "title": "Laos",
                "dates": "6/11 → 19/11 (14 jours)",
                "price": "4 950 €",
                "links": [
                    {"label":"Infos","href":"https://pulsionhorizon.com/lelaos"},
                    {"label":"Vidéo","href":"https://youtu.be/JBhY8BF7emw?si=H6SnVk2Kq0mHpNF8"},
                ],
                "code": "LAOS-2026-01",
            },

            # --- Sénégal / 4x4 / XT600 ---
            {"divider": "Découverte Sénégal — moto & 4×4"},

            {
                "title": "Circuit Sénégal 4×4",
                "dates": "8 jours (mixte découverte/safari/détente)",
                "price": "à partir de 339 €",
                "links": [
                    {"label":"Infos","href":"https://pulsionhorizon.com/circuit-4x4"},
                    {"label":"Reportage (4 filles)","href":"https://www.youtube.com/watch?v=AwOpUqKkL7k&list=PLdMDxuSlIsrufx6QPnG2horXLzsQTyqxW&pp=gAQBiAQB"},
                ],
                "code": "SENEGAL-4X4-2026-01",
            },
            {
                "title": "Circuit Yam XT 600",
                "dates": "10 jours (dès 2 pilotes, max 10)",
                "price": "1 190 €",
                "links": [
                    {"label":"Infos","href":"https://pulsionhorizon.com/circuit-moto-xt-600"},
                    {"label":"Épopée au Sénégal (1 jour)","href":"https://youtu.be/TKnj8TPg5Jo?feature=shared"},
                    {"label":"Playlist XT600","href":"https://www.youtube.com/watch?v=9cafohB7oQE&list=PLdMDxuSlIsrtHpzIjbspNVcX_GAYpyNXG&pp=gAQBiAQB"},
                ],
                "code": "XT600-SENEGAL-2026-01",
            },
        ],
    },
}

def programmes_index(request):
    years = sorted(PROGRAMMES.keys(), reverse=True)
    cards = [{"annee": y, "count": sum(1 for it in PROGRAMMES[y]["items"] if "divider" not in it)} for y in years]
    return render(request, "circuitMoto/programmes/programme.html", {"cards": cards})

def programme_detail(request, annee:int):
    if annee not in PROGRAMMES:
        raise Http404("Programme introuvable.")
    data = PROGRAMMES[annee]

    # 1) Séparer en sections
    sections = []
    current = {"title": None, "items": []}
    for it in data["items"]:
        if "divider" in it:
            if current["items"]:
                sections.append(current)
            current = {"title": it["divider"], "items": []}
        else:
            current["items"].append(it)
    if current["items"]:
        sections.append(current)

    # 2) Résoudre circuit_id depuis code (si présent)
    for sec in sections:
        for it in sec["items"]:
            if "circuit_id" not in it:  # pas déjà fixé en dur
                code = it.get("code")
                if code:
                    c = (Circuit.objects
                         .filter(code=code, statut="PUBLIE")
                         .only("id")
                         .first())
                    if c:
                        it["circuit_id"] = c.id

    return render(request, "circuitMoto/programmes/detail.html", {
        "annee": annee,
        "intro": data["intro"],
        "sections": sections,
    })

@require_POST
def newsletter_subscribe(request):
    email = (request.POST.get("email") or "").strip().lower()
    if not email:
        return JsonResponse({"ok": False, "message": "Adresse e-mail requise."}, status=400)
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"ok": False, "message": "Adresse e-mail invalide."}, status=400)

    source = (request.POST.get("source") or "footer")[:100]

    try:
        with transaction.atomic():
            sub, created = NewsletterSubscriber.objects.get_or_create(
                email=email, defaults={"source": source}
            )
            if created:
                return JsonResponse({"ok": True, "status": "created",
                                     "message": "Merci ! Vous êtes inscrit·e à la newsletter."})
            if not sub.is_active:
                sub.is_active = True
                if not sub.source:
                    sub.source = source
                sub.save(update_fields=["is_active", "source"])
                return JsonResponse({"ok": True, "status": "reactivated",
                                     "message": "Abonnement réactivé."})
            return JsonResponse({"ok": True, "status": "exists",
                                 "message": "Vous êtes déjà inscrit·e."})
    except IntegrityError:
        return JsonResponse({"ok": True, "status": "exists",
                             "message": "Vous êtes déjà inscrit·e."})

def _collect_hero_slides(circuit) -> List[Dict[str, str]]:
    """
    Construit une petite galerie d'images pour le HERO.
    Priorités :
    1) circuit.image
    2) circuit.images.all() (si un M2M/related existe)
    3) URLs saisies en texte libre dans circuit.galerie_urls (1 URL par ligne)
    """
    slides = []

    # 1) Image principale
    try:
        if getattr(circuit, "image", None) and getattr(circuit.image, "url", ""):
            slides.append({"url": circuit.image.url, "caption": circuit.nom or ""})
    except Exception:
        pass

    # 2) Related images (si présent dans ton modèle)
    try:
        imgs = list(getattr(circuit, "images", []).all()[:8])
        for im in imgs:
            url = getattr(getattr(im, "image", None), "url", "") or getattr(im, "url", "")
            if url:
                slides.append({"url": url, "caption": getattr(im, "legende", "") or circuit.nom or ""})
    except Exception:
        pass

    # 3) Champ texte "galerie_urls" (une URL par ligne) — optionnel
    raw_urls = (getattr(circuit, "galerie_urls", "") or "").strip()
    if raw_urls:
        for line in raw_urls.replace("\r", "").split("\n"):
            u = line.strip()
            if u and re.match(r"^https?://", u, flags=re.I):
                slides.append({"url": u, "caption": circuit.nom or ""})

    # Unicité simple sur l’URL
    uniq, seen = [], set()
    for s in slides:
        if s["url"] not in seen:
            uniq.append(s)
            seen.add(s["url"])
    return uniq[:10]  # on limite raisonnablement

def circuit_detail_pk_redirect(request, pk: int):
    qs = Circuit.objects.only("code", "statut")
    if not request.user.is_staff:
        qs = qs.filter(statut="PUBLIE")
    circuit = get_object_or_404(qs, pk=pk)
    # Django sait utiliser obj.get_absolute_url directement
    return redirect(circuit, permanent=True)

def _normalize_num(num_str: str) -> Optional[float]:
    if not num_str:
        return None
    s = (num_str
         .replace('\u00A0', '')   # NBSP
         .replace('\u202F', '')   # NNBSP
         .replace(' ', '')
         .replace(',', '.'))
    try:
        return float(s)
    except ValueError:
        return None

def _tokenize_kms(text: str) -> List[str]:
    """
    Découpe un bloc 'kilométrages' en items par séparateurs usuels : • | ; retours à la ligne.
    """
    if not text:
        return []
    # normalise retours
    t = text.replace('\r', '')
    parts = re.split(r'[•\u2022\|\n;]+', t)
    return [p.strip() for p in parts if p.strip()]

def _parse_kilometrages(text: str):
    items = []
    by_id: Dict[str, int] = {}

    # Supporte: "Option J1A …", "Jour 1A …", "J1A …"
    day_re  = re.compile(r'^(?:Option\s+)?(?:(?:Jour|J)\s*)?(?P<id>\d+[A-Z]?)\b', re.IGNORECASE)
    km_re   = re.compile(r'(?P<km>\d{1,3}(?:[ \u00A0\u202F]?\d{3})*(?:[.,]\d+)?)\s*km\b', re.IGNORECASE)
    idem_re = re.compile(r'idem\s+J(?P<ref>\d+[A-Z]?)', re.IGNORECASE)

    for tok in _tokenize_kms(text):
        if tok.lower().startswith('total'):
            continue

        mday = day_re.search(tok)
        if not mday:
            continue

        id_raw = mday.group('id').upper()
        label  = f'J{id_raw}'

        # option si la ligne commence par "Option " OU si "(OPTION)" apparaît quelque part
        is_opt = tok.strip().lower().startswith('option ') or bool(re.search(r'\(\s*option\s*\)', tok, re.IGNORECASE))

        km_val = None
        mkm = km_re.search(tok)
        if mkm:
            f = _normalize_num(mkm.group('km'))
            if f is not None:
                km_val = int(round(f))

        if km_val is None:
            midem = idem_re.search(tok)
            if midem:
                ref = midem.group('ref').upper()
                km_val = by_id.get(ref)

        km_int = int(km_val) if isinstance(km_val, (int, float)) else 0

        items.append({"id": id_raw, "label": label, "km": km_int, "is_option": is_opt, "raw": tok})
        if km_int:
            by_id[id_raw] = km_int

    total_base = sum(i["km"] for i in items if not i["is_option"])
    total_with_options = sum(i["km"] for i in items)
    return items, {"base": total_base, "with_options": total_with_options}

def _split_bullets(text: str):
    """
    Transforme un bloc texte en puces (ligne par ligne),
    en ignorant les lignes vides et en normalisant les tirets / puces.
    """
    if not text:
        return []
    rows = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # supprime un éventuel bullet de départ (•, -, *, • )
        line = re.sub(r'^[\-\*\u2022]\s+', '', line)
        rows.append(line)
    return rows

def _parse_programme(text: str):
    """
    Découpe 'Programme' en sections "Jour X" (ex. "Jour 1A (OPTION) — 06/05 …").
    Supporte les bullets ("•", "-", "*") devant la ligne.
    """
    if not text:
        return []

    # 1) lignes non vides + suppression d'un bullet éventuel au début
    lines = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        s = re.sub(r'^[\-\*\u2022•]\s*', '', s)  # retire puce de départ
        lines.append(s)

    items, cur = [], None
    # “Jour 1”, “Jour 1A”, puis n'importe quel libellé
    is_title = lambda l: re.match(r'^\s*jour\s+\d+[A-Z]?(?:\b|[^a-z])', l, flags=re.I)

    for line in lines:
        if is_title(line):
            if cur:
                items.append(cur)
            cur = {"title": line, "body": []}
        else:
            if cur is None:
                cur = {"title": "Programme", "body": []}
            cur["body"].append(line)

    if cur:
        cur["body"] = "\n".join(cur["body"])
        items.append(cur)
        # normalise le body de tous
        for it in items:
            if isinstance(it["body"], list):
                it["body"] = "\n".join(it["body"])

    return items

def _group_options(options_qs):
    grouped = defaultdict(list)
    for o in options_qs:
        label = o.get_categorie_display() if hasattr(o, "get_categorie_display") else (o.categorie or "Options")
        grouped[label].append(o)
    # On renvoie une liste triée pour un rendu stable
    return [{"categorie": k, "items": v} for k, v in grouped.items()]

def _first_present(mapping, *keys):
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None

def _as_float(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None

def _normalise_route_point(raw, fallback_label=""):
    if isinstance(raw, dict):
        lat = _as_float(_first_present(raw, "lat", "latitude"))
        lng = _as_float(_first_present(raw, "lng", "lon", "longitude"))
        label = _first_present(raw, "label", "name", "title", "ville", "city") or fallback_label
        kind = _first_present(raw, "type", "kind") or ""
    elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
        lat = _as_float(raw[0])
        lng = _as_float(raw[1])
        label = str(raw[2]) if len(raw) >= 3 and raw[2] not in (None, "") else fallback_label
        kind = ""
    else:
        return None

    if lat is None or lng is None:
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None

    return {
        "label": str(label or "Etape"),
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "type": str(kind or ""),
    }

def _normalise_street_view(raw, default_point=None):
    if not isinstance(raw, dict):
        raw = {}
    lat = _as_float(_first_present(raw, "lat", "latitude"))
    lng = _as_float(_first_present(raw, "lng", "lon", "longitude"))
    if (lat is None or lng is None) and default_point:
        lat = default_point.get("lat")
        lng = default_point.get("lng")
    if lat is None or lng is None:
        return None
    return {
        "lat": round(float(lat), 6),
        "lng": round(float(lng), 6),
        "heading": _as_float(_first_present(raw, "heading", "cap")) or 0,
        "pitch": _as_float(_first_present(raw, "pitch")) or 0,
        "zoom": _as_float(_first_present(raw, "zoom")) or 1,
    }

def _google_route_url(points):
    if not points:
        return ""
    if len(points) == 1:
        query = quote(f"{points[0]['lat']},{points[0]['lng']}")
        return f"https://www.google.com/maps/search/?api=1&query={query}"

    origin = quote(f"{points[0]['lat']},{points[0]['lng']}")
    destination = quote(f"{points[-1]['lat']},{points[-1]['lng']}")
    url = f"https://www.google.com/maps/dir/?api=1&travelmode=driving&origin={origin}&destination={destination}"
    waypoints = points[1:-1]
    if waypoints:
        url += "&waypoints=" + quote("|".join(f"{p['lat']},{p['lng']}" for p in waypoints), safe="")
    return url

def _prepare_itineraire(circuit):
    raw_days = getattr(circuit, "itineraire_points", None) or []
    if isinstance(raw_days, dict):
        raw_days = [raw_days]
    if not isinstance(raw_days, list):
        raw_days = []

    days = []
    for index, raw_day in enumerate(raw_days, start=1):
        if not isinstance(raw_day, dict):
            continue

        day_label = _first_present(raw_day, "day", "jour", "label") or f"Jour {index}"
        title = _first_present(raw_day, "title", "name", "ville", "city") or day_label
        points_raw = _first_present(raw_day, "points", "stops", "etapes", "waypoints") or []
        if not points_raw and _first_present(raw_day, "lat", "latitude") is not None:
            points_raw = [raw_day]

        points = []
        for p_index, point_raw in enumerate(points_raw, start=1):
            point = _normalise_route_point(point_raw, fallback_label=f"{day_label} - {p_index}")
            if point:
                points.append(point)

        street_raw = _first_present(raw_day, "street_view", "streetView", "panorama") or {}
        street_view = _normalise_street_view(street_raw, points[0] if points else None)
        maps_url = _first_present(raw_day, "maps_url", "mapsUrl", "url") or _google_route_url(points)

        if not points and not maps_url:
            continue

        days.append({
            "index": len(days),
            "day": str(day_label),
            "title": str(title),
            "description": str(_first_present(raw_day, "description", "body", "summary") or ""),
            "distance": str(_first_present(raw_day, "distance", "km", "kilometrage") or ""),
            "duration": str(_first_present(raw_day, "duration", "temps", "time") or ""),
            "points": points,
            "streetView": street_view,
            "mapsUrl": maps_url,
        })

    all_points = [point for day in days for point in day["points"]]
    if all_points:
        center = {
            "lat": round(sum(p["lat"] for p in all_points) / len(all_points), 6),
            "lng": round(sum(p["lng"] for p in all_points) / len(all_points), 6),
        }
    else:
        center = None

    generated_maps_url = _google_route_url(all_points)
    maps_url = (getattr(circuit, "itineraire_google_maps_url", "") or generated_maps_url or "").strip()
    embed_url = (getattr(circuit, "itineraire_embed_url", "") or "").strip()
    street_url = (getattr(circuit, "itineraire_street_view_url", "") or "").strip()
    enabled = bool(getattr(circuit, "itineraire_active", False) and (days or maps_url or embed_url or street_url))

    return {
        "enabled": enabled,
        "title": getattr(circuit, "nom", "") or "",
        "center": center,
        "days": days,
        "mapsUrl": maps_url,
        "embedUrl": embed_url,
        "streetViewUrl": street_url,
        "hasCoordinates": bool(all_points),
        "pointCount": len(all_points),
    }

def circuit_detail(request, code: str):
    qs = (Circuit.objects
        .annotate(nb_inscriptions=Count("inscriptions"))

        .prefetch_related(
            Prefetch(
                "options",
                queryset=OptionCircuit.actifs.order_by("cree_le", "id")
            )
        ))

    # côté public on ne montre que les PUBLIE
    if not request.user.is_staff:
        qs = qs.filter(statut="PUBLIE")

    circuit = get_object_or_404(qs, code=code)

    # KPIs utiles pour l'affichage
    capacite = circuit.capacite or 0
    nb = circuit.nb_inscriptions or 0
    pct = int(round((nb / capacite) * 100)) if capacite else 0
    duree_jours = (circuit.date_fin - circuit.date_debut).days + 1 if circuit.date_debut and circuit.date_fin else None

    # Préparations de contenu
    programme_items = _parse_programme(getattr(circuit, "programme", "") or "")

    programme_items = _parse_programme(getattr(circuit, "programme", "") or "")

    # --- NEW: détacher l'introduction éventuelle ("Programme") de la timeline ---
    programme_intro = ""
    if programme_items and str(programme_items[0].get("title", "")).strip().lower().startswith("programme"):
        programme_intro = programme_items[0].get("body", "") or ""
        programme_items = programme_items[1:]  # on ne garde que les "Jour …" dans la timeline


    # kms_items = _split_bullets(getattr(circuit, "kilometrages", "") or "")
    kms_struct, kms_totals = _parse_kilometrages(getattr(circuit, "kilometrages", "") or "")
    kms_raw = _split_bullets(getattr(circuit, "kilometrages", "") or "")  # fallback

    comprend_items = _split_bullets(getattr(circuit, "prix_comprend", "") or "")
    ne_comprend_pas_items = _split_bullets(getattr(circuit, "prix_ne_comprend_pas", "") or "")
    options_grouped = _group_options(
        circuit.options.filter(actif=True)
    )

    # Échéancier: on n’invente pas de montants — on affiche d’abord le texte libre
    echeancier_texte = (getattr(circuit, "echeancier_texte", "") or "").strip()

    hero_slides = _collect_hero_slides(circuit)
    itineraire = _prepare_itineraire(circuit)

    ctx = {
        "circuit": circuit,
        "pct": pct,
        "duree_jours": duree_jours,
        "programme_items": programme_items,
        # "kms_items": kms_items,
        "kms_struct": kms_struct,
        "kms_totals": kms_totals,
        "kms_items": kms_raw,
        "programme_intro": programme_intro,
        "comprend_items": comprend_items,
        "ne_comprend_pas_items": ne_comprend_pas_items,
        "options_grouped": options_grouped,
        "echeancier_texte": echeancier_texte,
        "hero_slides": hero_slides,
        "itineraire": itineraire,
        "google_maps_api_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
    }

    # === AUTRES CIRCUITS (seulement publiés ET à venir) ===
    today = timezone.localdate()

    others_qs = (
        Circuit.objects
        .annotate(nb_inscr=Count("inscriptions"))
        .exclude(pk=circuit.pk)
        .filter(statut="PUBLIE", date_debut__gte=today)  # <= filtre clé
        .order_by("date_debut", "id")
    )

    others_list = list(others_qs)

    for o in others_list:
        # durée (jours)
        o.duree_jours = (o.date_fin - o.date_debut).days + 1 if (o.date_debut and o.date_fin) else None

        # remplissage / disponibilité
        cap = o.capacite or 0
        nb_o = getattr(o, "nb_inscr", 0) or 0
        o.pct_remplissage = int(round((nb_o / cap) * 100)) if cap else 0
        o.est_disponible = (o.statut == "PUBLIE" and o.pct_remplissage < 100)

        # kilométrage total (base, hors options)
        try:
            _items_o, _totals_o = _parse_kilometrages(getattr(o, "kilometrages", "") or "")
            o.kilometrage_total = _totals_o["base"]
        except Exception:
            o.kilometrage_total = None

        # badge "Nouveau" (optionnel)
        try:
            o.est_nouveau = bool(getattr(o, "cree_le", None) and (timezone.now() - o.cree_le).days <= 60)
        except Exception:
            o.est_nouveau = False

    paginator = Paginator(others_list, 6)
    page_number = request.GET.get("page") or 1
    autres_page = paginator.get_page(page_number)
    ctx["autres_circuits"] = autres_page



    return render(request, "circuitMoto/circuit_detail.html", ctx)

def inscription_lookup(request):
    """Page Déjà inscrit ? -> saisie de la référence, vérification, redirection si trouvée."""
    ref = (request.GET.get("ref") or "").strip()
    ctx = {"prefill": ref}

    if ref:
        try:
            uid = uuid.UUID(ref)  # valide le format
        except ValueError:
            messages.error(request, "Référence invalide. Merci de vérifier le format.")
            return render(request, "circuitMoto/inscription/lookup.html", ctx)

        ins = Inscription.objects.filter(id_public=uid).first()
        if not ins:
            messages.error(request, "Aucune inscription trouvée pour cette référence.")
            return render(request, "circuitMoto/inscription/lookup.html", ctx)

        # OK -> on redirige vers le wizard d’édition
        return redirect("inscription_edit_start", id_public=str(ins.id_public))

    return render(request, "circuitMoto/inscription/lookup.html", ctx)

class CircuitPublicList(ListView):
    template_name = "circuitMoto/circuits_list.html"
    context_object_name = "circuits"
    paginate_by = 6

    def get_queryset(self):
        # date du jour
        today = getattr(timezone, "localdate", None)
        today = today() if today else timezone.now().date()

        q = (self.request.GET.get("q") or "").strip()

        qs = (
            Circuit.objects
            .filter(
                statut=StatutCircuit.PUBLIE,   # ← au lieu de publie=True
                date_fin__gte=today,
            )
            .order_by("date_debut", "code")
        )
        if q:
            qs = qs.filter(
                Q(nom__icontains=q) | Q(description__icontains=q) | Q(code__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = (self.request.GET.get("q") or "").strip()
        return ctx
    
from django.views.decorators.http import require_http_methods, require_GET
@require_GET
def api_circuits_by_statut(request):
    statut = (request.GET.get("statut") or "").upper()

    # Limiter aux 2 statuts autorisés
    if statut not in (StatutCircuit.PUBLIE, StatutCircuit.ARCHIVE):
        return JsonResponse({"results": []})

    qs = (
        Circuit.objects
        .filter(statut=statut)
        .order_by("-date_debut")
        .only("id", "code", "nom", "date_debut", "date_fin")
    )

    results = [{
        "id": c.id,
        "code": c.code,
        "nom": c.nom,
        "date_debut": c.date_debut.isoformat() if c.date_debut else None,
        "date_fin": c.date_fin.isoformat() if c.date_fin else None,
        "url": request.build_absolute_uri(c.get_absolute_url()),
    } for c in qs]

    return JsonResponse({"results": results})

SPAM_RE = re.compile(r'https?://|www\.|promo code|urgent message|winning move|casino|crypto|telegram', re.I)

def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()

def _rate_key_ip(ip: str) -> str:
    return f"contact_rate_ip:{ip}:{timezone.now().strftime('%Y%m%d%H')}"

def _rate_key_email(email: str) -> str:
    email = (email or "").strip().lower()
    return f"contact_rate_email:{email}:{timezone.now().strftime('%Y%m%d')}"

def _rate_limited(ip: str, email: str = "") -> bool:
    try:
        ip_key = _rate_key_ip(ip)
        ip_count = cache.get(ip_key, 0)
        if ip_count >= 3:
            return True
        cache.set(ip_key, ip_count + 1, 3600)

        if email:
            email_key = _rate_key_email(email)
            email_count = cache.get(email_key, 0)
            if email_count >= 2:
                return True
            cache.set(email_key, email_count + 1, 86400)
    except Exception:
        pass
    return False

def _looks_like_spam(cm: ContactMessage) -> bool:
    payload = " ".join([
        cm.nom or "",
        cm.prenom or "",
        cm.email or "",
        cm.telephone or "",
        cm.message or "",
    ])
    return bool(SPAM_RE.search(payload))

@require_http_methods(["GET", "POST"])
def contact(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        request.session["contact_form_loaded_at"] = int(timezone.now().timestamp())
        form = ContactForm()
        return render(request, "circuitMoto/contact.html", {"form": form})

    statut_init = (request.POST.get("statut_circuit") or "").upper()
    form = ContactForm(request.POST, statut_init=statut_init)

    ip = _client_ip(request)
    email_post = (request.POST.get("email") or "").strip().lower()

    if _rate_limited(ip, email_post):
        messages.error(request, _("Trop de demandes récentes. Réessayez plus tard."))
        return render(request, "circuitMoto/contact.html", {"form": form})

    loaded_at = request.session.get("contact_form_loaded_at")
    now_ts = int(timezone.now().timestamp())
    if loaded_at and (now_ts - int(loaded_at)) < 3:
        messages.error(request, _("Soumission trop rapide. Réessayez."))
        return render(request, "circuitMoto/contact.html", {"form": form})

    raw_message = (request.POST.get("message") or "").lower()

    if "http://" in raw_message or "https://" in raw_message or "www." in raw_message:
        messages.error(request, _("Votre message n’a pas pu être envoyé."))
        return render(request, "circuitMoto/contact.html", {"form": form})

    if form.is_valid():
        cm: ContactMessage = form.save(commit=False)
        cm.ip = ip
        cm.user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:255]

        if _looks_like_spam(cm):
            messages.error(request, _("Votre message n’a pas pu être envoyé."))
            return render(request, "circuitMoto/contact.html", {"form": form})

        cm.save()

        admin_to = getattr(settings, "NOTIFY_ADMIN_EMAIL", settings.DEFAULT_FROM_EMAIL)
        ctx = {"cm": cm, "site_url": getattr(settings, "SITE_URL", request.build_absolute_uri("/"))}

        subject_admin = f"[Contact] {cm.type_demande} — {cm.nom} {cm.prenom}"
        body_txt = render_to_string("emails/contact_admin.txt", ctx)
        body_html = render_to_string("emails/contact_admin.html", ctx)
        m_admin = EmailMultiAlternatives(subject_admin, body_txt, settings.DEFAULT_FROM_EMAIL, [admin_to])
        m_admin.attach_alternative(body_html, "text/html")
        m_admin.send(fail_silently=True)

        subject_user = _("Votre demande a bien été reçue")
        body_txt_u = render_to_string("emails/contact_user_ack.txt", ctx)
        body_html_u = render_to_string("emails/contact_user_ack.html", ctx)
        m_user = EmailMultiAlternatives(subject_user, body_txt_u, settings.DEFAULT_FROM_EMAIL, [cm.email])
        m_user.attach_alternative(body_html_u, "text/html")
        m_user.send(fail_silently=True)

        messages.success(request, _("Merci ! Votre message a bien été envoyé."))
        return redirect("contact")

    return render(request, "circuitMoto/contact.html", {"form": form})

# =========================
# BALADES 1 JOUR
# =========================

BALADES_LINK_META = {
    "moto-zenith-huy-namur-le-condroz": {
        "partner_name": "Moto Zenith Huy",
        "title": "Balade Moto Zenith Huy",
        "subtitle": "Recevez le programme de la balade proposée au départ de Moto Zenith Huy.",
        "logo": "circuitMoto/images/logo/logo_moto_zenith.png",
        "logo_alt": "Logo Moto Zenith Huy",
    },
    "zone-rouge": {
        "partner_name": "Moto Zone Rouge",
        "title": "Balades Moto Zone Rouge",
        "subtitle": "Recevez le programme des balades Zone Rouge selon les dates proposées.",
        "logo": "circuitMoto/images/logo/Logo_zone_rouge.webp",
        "logo_alt": "Logo Moto Zone Rouge",
    },
    "ducati-sambreville-le-namurois": {
        "partner_name": "Ducati Sambreville",
        "title": "Balade Ducati Sambreville",
        "subtitle": "Recevez le programme de la balade proposée au départ de Ducati Sambreville.",
        "logo": "circuitMoto/images/logo/logo_duc_sambreville.jpg",
        "logo_alt": "Logo Ducati Sambreville",
    },
    "jl-selection-neufchateau-ardennes": {
        "partner_name": "JL Selection Neufchateau",
        "title": "Balade JL Selection Neufchateau",
        "subtitle": "Recevez le programme de la balade proposée au départ de JL Selection Neufchateau.",
        "logo": "circuitMoto/images/logo/logo_jl_selection.webp",
        "logo_alt": "Logo JL Selection Neufchateau",
    },
    "moto-casu-mons-vers-leaux-dheure": {
        "partner_name": "Moto Casu Mons",
        "title": "Balade Moto Casu Mons",
        "subtitle": "Recevez le programme de la balade proposée au départ de Moto Casu Mons.",
        "logo": "circuitMoto/images/logo/logo_casu.jpg",
        "logo_alt": "Logo Moto Casu Mons",
    },
    "harley-liege-le-liegeois": {
        "partner_name": "Harley Liège",
        "title": "Balade Harley Liège",
        "subtitle": "Recevez le programme de la balade proposée au départ de Harley Liège.",
        "logo": "circuitMoto/images/logo/logo_harley.jpg",
        "logo_alt": "Logo Harley Liège",
    },
    "xm-moto-namur-ardennes": {
        "partner_name": "XM Moto",
        "title": "Balade XM Moto",
        "subtitle": "Recevez le programme de la balade proposée au départ de XM Moto.",
        "logo": "circuitMoto/images/logo/logo_xm_bikes.jpg",
        "logo_alt": "Logo XM Moto",
    },
}

BALADES_DETAIL_IMAGES = {
    "moto-casu-mons-vers-leaux-dheure": "circuitMoto/images/images_balade_detail/casu-moto.jpg",
    "ducati-sambreville-le-namurois": "circuitMoto/images/images_balade_detail/DucatiSambreville.webp",
    "harley-liege-le-liegeois": "circuitMoto/images/images_balade_detail/harley.webp",
    "moto-zenith-huy-namur-le-condroz": "circuitMoto/images/images_balade_detail/motozenith.jpg",
    "xm-moto-namur-ardennes": "circuitMoto/images/images_balade_detail/xm-moto.webp",
    "zone-rouge": "circuitMoto/images/images_balade_detail/Zone-rouge-moto.webp",
}

BALADES_DETAIL_DEFAULT_IMAGE = "circuitMoto/images/presentation_balade_1_jour.jpg"

def _get_balade_detail_image(source: str, landing_meta=None) -> str:
    """
    Retourne l'image à afficher dans la page balades_1_jour.html.
    Priorité :
    1) image liée au slug partenaire
    2) image par défaut actuelle
    """
    if source.startswith("page_balades_1_jour_lien_"):
        slug = source.replace("page_balades_1_jour_lien_", "", 1).strip().lower()
        if slug in BALADES_DETAIL_IMAGES:
            return BALADES_DETAIL_IMAGES[slug]

    return BALADES_DETAIL_DEFAULT_IMAGE

def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def _client_ip_balades(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


def _rate_limit_balades(ip: str, window_sec: int = 600, max_hits: int = 8) -> bool:
    """
    True => bloqué
    8 soumissions max / 10 min / IP
    """
    if not ip:
        return False

    digest = hashlib.sha256(ip.encode("utf-8")).hexdigest()
    key = f"balades_rl:{digest}"

    current = cache.get(key, 0)

    if current >= max_hits:
        return True

    if current == 0:
        cache.set(key, 1, timeout=window_sec)
    else:
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, current + 1, timeout=window_sec)

    return False


def _is_duplicate_balades_submission(
    email: str,
    prenom: str,
    nom: str,
    balades_ids: List[int],
    ttl_sec: int = 900,
) -> bool:
    """
    Empêche les resoumissions identiques à très court terme.
    Clé de cache hashée pour être compatible memcached.
    """
    base = "|".join([
        _normalize_text(email),
        _normalize_text(prenom),
        _normalize_text(nom),
        ",".join(str(x) for x in sorted(balades_ids)),
    ])

    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()
    key = f"balades_dup:{digest}"

    if cache.get(key):
        return True

    cache.set(key, 1, timeout=ttl_sec)
    return False


def _balades_queryset_for_code(code: Optional[str] = None):
    qs = BaladeJour.objects.filter(actif=True).order_by("date_debut", "ordre", "titre")
    if code:
        qs = qs.filter(code_lien=code)
    return qs


def _render_balades_form(
    request,
    *,
    balades_qs,
    source: str,
    landing_meta=None,
):
    """
    Logique unique partagée par :
    - la page générale /balades-1-jour/
    - les liens garage /balades-1-jour/lien/<code>/
    """
    if request.method == "GET":
        request.session["balades_form_loaded_at"] = int(timezone.now().timestamp())
        request.session["balades_form_token"] = secrets.token_urlsafe(24)

        form = DemandeProgrammeBaladeForm(balades_queryset=balades_qs)
        detail_image = _get_balade_detail_image(source=source, landing_meta=landing_meta)

        return render(
            request,
            "circuitMoto/balades_1_jour.html",
            {
                "form": form,
                "balades": balades_qs,
                "balades_form_token": request.session.get("balades_form_token", ""),
                "is_partner_landing": bool(landing_meta),
                "landing_meta": landing_meta,
                "detail_image": detail_image,
            },
        )

    ip = _client_ip_balades(request)

    # 1) Rate limit IP
    if _rate_limit_balades(ip, window_sec=600, max_hits=8):
        messages.error(
            request,
            "Trop de tentatives détectées. Merci de réessayer un peu plus tard."
        )
        form = DemandeProgrammeBaladeForm(request.POST, balades_queryset=balades_qs)
        detail_image = _get_balade_detail_image(source=source, landing_meta=landing_meta)
        return render(
            request,
            "circuitMoto/balades_1_jour.html",
            {
                "form": form,
                "balades": balades_qs,
                "balades_form_token": request.session.get("balades_form_token", ""),
                "is_partner_landing": bool(landing_meta),
                "landing_meta": landing_meta,
                "detail_image": detail_image,
            },
            status=429,
        )

    form = DemandeProgrammeBaladeForm(request.POST, balades_queryset=balades_qs)

    # 2) Vérification token de formulaire
    session_token = request.session.get("balades_form_token", "")
    posted_token = (request.POST.get("form_token") or "").strip()

    if not session_token or not posted_token or posted_token != session_token:
        messages.error(request, "Session de formulaire invalide. Merci de recharger la page.")
        request.session["balades_form_token"] = secrets.token_urlsafe(24)
        detail_image = _get_balade_detail_image(source=source, landing_meta=landing_meta)
        return render(
            request,
            "circuitMoto/balades_1_jour.html",
            {
                "form": form,
                "balades": balades_qs,
                "balades_form_token": request.session.get("balades_form_token", ""),

                "is_partner_landing": bool(landing_meta),
                "landing_meta": landing_meta,
                "detail_image": detail_image,

            },
            status=400,
        )

    # Consomme le token immédiatement pour empêcher tout rejeu
    request.session["balades_form_token"] = secrets.token_urlsafe(24)

    # 3) Temps minimum
    loaded_at = request.session.get("balades_form_loaded_at")
    now_ts = int(timezone.now().timestamp())

    if loaded_at and (now_ts - int(loaded_at)) < 3:
        messages.error(request, "Soumission trop rapide. Merci de réessayer.")
        request.session["balades_form_token"] = secrets.token_urlsafe(24)
        detail_image = _get_balade_detail_image(source=source, landing_meta=landing_meta)
        return render(
            request,
            "circuitMoto/balades_1_jour.html",
            {
                "form": form,
                "balades": balades_qs,
                "balades_form_token": request.session.get("balades_form_token", ""),
                "is_partner_landing": bool(landing_meta),
                "landing_meta": landing_meta,
                "detail_image": detail_image,

            },
            status=400,
        )

    # 4) Temps maximum raisonnable de session formulaire
    if loaded_at and (now_ts - int(loaded_at)) > 60 * 60 * 6:
        messages.error(request, "Votre session a expiré. Merci de recharger la page.")
        request.session["balades_form_loaded_at"] = int(timezone.now().timestamp())
        request.session["balades_form_token"] = secrets.token_urlsafe(24)
        detail_image = _get_balade_detail_image(source=source, landing_meta=landing_meta)
        return render(
            request,
            "circuitMoto/balades_1_jour.html",
            {
                "form": form,
                "balades": balades_qs,
                "balades_form_token": request.session.get("balades_form_token", ""),
                "is_partner_landing": bool(landing_meta),
                "landing_meta": landing_meta,
                "detail_image": detail_image,

            },
            status=400,
        )

    if form.is_valid():
        balades_ids = list(form.cleaned_data["balades"].values_list("id", flat=True))

        # 5) Bloque doublons très rapprochés
        if _is_duplicate_balades_submission(
            email=form.cleaned_data.get("email", ""),
            prenom=form.cleaned_data.get("prenom", ""),
            nom=form.cleaned_data.get("nom", ""),
            balades_ids=balades_ids,
            ttl_sec=900,
        ):
            messages.error(
                request,
                "Une demande identique a déjà été reçue récemment. Merci de patienter avant de renvoyer."
            )
            request.session["balades_form_token"] = secrets.token_urlsafe(24)
            detail_image = _get_balade_detail_image(source=source, landing_meta=landing_meta)
            return render(
                request,
                "circuitMoto/balades_1_jour.html",
                {
                    "form": form,
                    "balades": balades_qs,
                    "balades_form_token": request.session.get("balades_form_token", ""),

                    "is_partner_landing": bool(landing_meta),
                    "landing_meta": landing_meta,
                    "detail_image": detail_image,

                },
                status=400,
            )

        with transaction.atomic():
            demande = form.save(commit=False)
            demande.source = source
            demande.ip = ip
            demande.user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:255]
            demande.save()
            form.save_m2m()

        try:
            notify_demande_balades_admin(demande, request=request)
        except Exception:
            pass

        try:
            notify_demande_balades_user_ack(demande, request=request)
        except Exception:
            pass

        # Renouvelle les infos de session après succès
        request.session["balades_form_loaded_at"] = int(timezone.now().timestamp())
        request.session["balades_form_token"] = secrets.token_urlsafe(24)

        messages.success(
            request,
            "Merci ! Votre sélection a bien été envoyée. Nous vous transmettrons les programmes correspondants dans les meilleurs délais."
        )
        return redirect("balades_1_jour_success")

    request.session["balades_form_token"] = secrets.token_urlsafe(24)
    detail_image = _get_balade_detail_image(source=source, landing_meta=landing_meta)

    return render(
        request,
        "circuitMoto/balades_1_jour.html",
        {
            "form": form,
            "balades": balades_qs,
            "balades_form_token": request.session.get("balades_form_token", ""),

            "is_partner_landing": bool(landing_meta),
            "landing_meta": landing_meta,
            "detail_image": detail_image,

        },
        status=400,
    )


@require_http_methods(["GET", "POST"])
def balades_1_jour(request):
    balades_qs = _balades_queryset_for_code()
    return _render_balades_form(
        request,
        balades_qs=balades_qs,
        source="page_balades_1_jour",
    )


def _balades_queryset_for_slug(slug=None):
    qs = BaladeJour.objects.filter(actif=True).order_by("date_debut", "ordre", "titre")
    if slug:
        qs = qs.filter(slug_lien=slug)
    return qs


@require_http_methods(["GET", "POST"])
def balades_1_jour_lien(request, slug):
    slug = (slug or "").strip().lower()

    if not slug:
        raise Http404("Lien introuvable.")

    balades_qs = _balades_queryset_for_slug(slug)

    if not balades_qs.exists():
        raise Http404("Aucune balade active pour ce lien.")

    return _render_balades_form(
        request,
        balades_qs=balades_qs,
        source=f"page_balades_1_jour_lien_{slug}",
        landing_meta=BALADES_LINK_META.get(slug),
    )


def balades_1_jour_success(request):
    return render(request, "circuitMoto/balades_1_jour_success.html")


def balades_email_landing(request):
    """
    Petite page optionnelle si tu veux mettre un bouton dans tes emails
    qui renvoie vers une landing plus marketing avant le formulaire.
    """
    balades = (
        BaladeJour.objects
        .filter(actif=True)
        .order_by("date_debut", "ordre", "titre")
    )

    balades_count = balades.count()
    balades_featured = list(balades[:3])

    return render(
        request,
        "circuitMoto/balades_email_landing.html",
        {
            "balades": balades,
            "balades_count": balades_count,
            "balades_featured": balades_featured,
        },
    )


# =========================
# PRE PROGRAMME 2027
# =========================

def _programme_2027_queryset():
    return Programme2027Circuit.objects.filter(actif=True).order_by("ordre", "titre")


def _client_ip_programme_2027(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


def _rate_limit_programme_2027(ip: str, window_sec: int = 600, max_hits: int = 6) -> bool:
    if not ip:
        return False

    digest = hashlib.sha256(ip.encode("utf-8")).hexdigest()
    key = f"programme2027_rl:{digest}"
    current = cache.get(key, 0)

    if current >= max_hits:
        return True

    if current == 0:
        cache.set(key, 1, timeout=window_sec)
    else:
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, current + 1, timeout=window_sec)

    return False


def _safe_selection_participants(value: str, default: int = 1) -> int:
    try:
        parsed = int(value or default)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, 1), 12)


def _programme_2027_selection_payload(request, circuits):
    valid_levels = {choice[0] for choice in NiveauInteret2027.choices}
    payload = []

    for circuit in circuits:
        level = (request.POST.get(f"niveau_{circuit.pk}") or NiveauInteret2027.INTERESSE).strip()
        if level not in valid_levels:
            level = NiveauInteret2027.INTERESSE

        payload.append({
            "circuit": circuit,
            "niveau_interet": level,
            "participants": _safe_selection_participants(request.POST.get(f"participants_{circuit.pk}")),
            "mode_prefere": (request.POST.get(f"mode_{circuit.pk}") or "").strip()[:140],
            "commentaire": (request.POST.get(f"precision_{circuit.pk}") or "").strip()[:500],
        })

    return payload


def _is_duplicate_programme_2027_submission(email: str, prenom: str, nom: str, payload: list, ttl_sec: int = 900) -> bool:
    base = "|".join([
        _normalize_text(email),
        _normalize_text(prenom),
        _normalize_text(nom),
        ",".join(
            f"{row['circuit'].pk}:{row['niveau_interet']}:{row['participants']}:{_normalize_text(row['mode_prefere'])}"
            for row in payload
        ),
    ])
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()
    key = f"programme2027_dup:{digest}"

    if cache.get(key):
        return True

    cache.set(key, 1, timeout=ttl_sec)
    return False


def _render_programme_2027_page(request, *, form, circuits, form_token, status=200):
    circuit_list = list(circuits)
    selected_ids = set(request.POST.getlist("circuits")) if request.method == "POST" else set()
    valid_levels = {choice[0] for choice in NiveauInteret2027.choices}

    for circuit in circuit_list:
        key = str(circuit.pk)
        posted_level = (request.POST.get(f"niveau_{circuit.pk}") or NiveauInteret2027.INTERESSE).strip()
        circuit.is_selected = key in selected_ids
        circuit.posted_niveau = posted_level if posted_level in valid_levels else NiveauInteret2027.INTERESSE
        circuit.posted_participants = request.POST.get(f"participants_{circuit.pk}") or "1"
        circuit.posted_mode = request.POST.get(f"mode_{circuit.pk}") or ""
        circuit.posted_precision = request.POST.get(f"precision_{circuit.pk}") or ""

    total_circuits = len(circuit_list)
    return render(
        request,
        "circuitMoto/programme_2027.html",
        {
            "form": form,
            "circuits": circuit_list,
            "niveau_choices": NiveauInteret2027.choices,
            "programme_2027_form_token": form_token,
            "total_circuits": total_circuits,
        },
        status=status,
    )


@require_http_methods(["GET", "POST"])
def programme_2027(request):
    circuits_qs = _programme_2027_queryset()

    if request.method == "GET":
        request.session["programme_2027_form_loaded_at"] = int(timezone.now().timestamp())
        request.session["programme_2027_form_token"] = secrets.token_urlsafe(24)

        form = Programme2027InterestForm(circuits_queryset=circuits_qs)
        return _render_programme_2027_page(
            request,
            form=form,
            circuits=circuits_qs,
            form_token=request.session.get("programme_2027_form_token", ""),
        )

    ip = _client_ip_programme_2027(request)
    form = Programme2027InterestForm(request.POST, circuits_queryset=circuits_qs)

    if _rate_limit_programme_2027(ip):
        messages.error(request, "Trop de tentatives detectees. Merci de reessayer un peu plus tard.")
        return _render_programme_2027_page(
            request,
            form=form,
            circuits=circuits_qs,
            form_token=request.session.get("programme_2027_form_token", ""),
            status=429,
        )

    session_token = request.session.get("programme_2027_form_token", "")
    posted_token = (request.POST.get("form_token") or "").strip()
    if not session_token or not posted_token or posted_token != session_token:
        messages.error(request, "Session de formulaire invalide. Merci de recharger la page.")
        request.session["programme_2027_form_token"] = secrets.token_urlsafe(24)
        return _render_programme_2027_page(
            request,
            form=form,
            circuits=circuits_qs,
            form_token=request.session.get("programme_2027_form_token", ""),
            status=400,
        )

    request.session["programme_2027_form_token"] = secrets.token_urlsafe(24)

    loaded_at = request.session.get("programme_2027_form_loaded_at")
    now_ts = int(timezone.now().timestamp())

    if loaded_at and (now_ts - int(loaded_at)) < 3:
        messages.error(request, "Soumission trop rapide. Merci de reessayer.")
        return _render_programme_2027_page(
            request,
            form=form,
            circuits=circuits_qs,
            form_token=request.session.get("programme_2027_form_token", ""),
            status=400,
        )

    if loaded_at and (now_ts - int(loaded_at)) > 60 * 60 * 6:
        messages.error(request, "Votre session a expire. Merci de recharger la page.")
        request.session["programme_2027_form_loaded_at"] = int(timezone.now().timestamp())
        request.session["programme_2027_form_token"] = secrets.token_urlsafe(24)
        return _render_programme_2027_page(
            request,
            form=form,
            circuits=circuits_qs,
            form_token=request.session.get("programme_2027_form_token", ""),
            status=400,
        )

    if form.is_valid():
        selected_circuits = list(form.cleaned_data["circuits"])
        selection_payload = _programme_2027_selection_payload(request, selected_circuits)

        if _is_duplicate_programme_2027_submission(
            email=form.cleaned_data.get("email", ""),
            prenom=form.cleaned_data.get("prenom", ""),
            nom=form.cleaned_data.get("nom", ""),
            payload=selection_payload,
        ):
            messages.error(request, "Une demande identique a deja ete recue recemment. Merci de patienter avant de renvoyer.")
            return _render_programme_2027_page(
                request,
                form=form,
                circuits=circuits_qs,
                form_token=request.session.get("programme_2027_form_token", ""),
                status=400,
            )

        with transaction.atomic():
            demande = form.save(commit=False)
            demande.source = "pre_programme_2027"
            demande.ip = ip
            demande.user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:255]
            demande.save()

            Programme2027Selection.objects.bulk_create([
                Programme2027Selection(
                    demande=demande,
                    circuit=row["circuit"],
                    niveau_interet=row["niveau_interet"],
                    participants=row["participants"],
                    mode_prefere=row["mode_prefere"],
                    commentaire=row["commentaire"],
                )
                for row in selection_payload
            ])

        try:
            notify_programme_2027_admin(demande, request=request)
        except Exception:
            pass

        try:
            notify_programme_2027_user_ack(demande, request=request)
        except Exception:
            pass

        request.session["programme_2027_form_loaded_at"] = int(timezone.now().timestamp())
        request.session["programme_2027_form_token"] = secrets.token_urlsafe(24)

        messages.success(request, "Merci ! Votre interet pour le pre programme 2027 a bien ete envoye.")
        return redirect("programme_2027_success")

    return _render_programme_2027_page(
        request,
        form=form,
        circuits=circuits_qs,
        form_token=request.session.get("programme_2027_form_token", ""),
        status=400,
    )


def programme_2027_success(request):
    return render(request, "circuitMoto/programme_2027_success.html")


def programme(request):
    programme_title = "Programme 2026"

    programme_intro = (
        "Découvrez l’ensemble du programme 2026 Pulsion Horizon : balades d’un jour, "
        "circuits Europe, raids, grands voyages et découvertes au Sénégal. "
        "Cette page a été pensée pour offrir une lecture plus claire, plus élégante, "
        "plus immersive et plus fluide sur mobile comme sur grand écran."
    )

    programme_notice = (
        "En règle générale, sauf pour les destinations hors Europe, les circuits se font "
        "avec votre propre moto. Certaines formules permettent aussi la location au départ "
        "de la Belgique ou sur place selon la destination. Les dates, traversées et tarifs "
        "peuvent encore évoluer légèrement selon la logistique et les disponibilités."
    )

    inscription_url_default = reverse("inscription_create_start")

    sections = [
        {
            "slug": "balades-1-jour",
            "title": "Les balades d’un jour",
            "kicker": "Gratuit & convivial",
            "description": (
                "En collaboration avec différents partenaires, nos balades d’un jour sont gratuites "
                "et le café est offert avant le départ. Chaque balade dispose ici de son accès direct."
            ),
            "cta_label": "Voir toutes les balades",
            "cta_url": "https://pulsion-inscription.com/balades-1-jour/",
            "items": [
                {
                    "title": "XM Moto — Namur / Ardennes",
                    "dates": "04/07/2026",
                    "price": "Gratuit",
                    "primary_url": "https://pulsion-inscription.com/balades-1-jour/lien/xm-moto-namur-ardennes/",
                    "primary_label": "Voir la balade",
                    "registration_url": "https://pulsion-inscription.com/balades-1-jour/lien/xm-moto-namur-ardennes/",
                    "registration_label": "S’inscrire",
                    
                },
                {
                    "title": "Moto Zenith Huy / Condroz",
                    "dates": "11/04/2026",
                    "price": "Gratuit",
                    "primary_url": "https://pulsion-inscription.com/balades-1-jour/lien/moto-zenith-huy-namur-le-condroz/",
                    "primary_label": "Voir la balade",
                    "registration_url": "https://pulsion-inscription.com/balades-1-jour/lien/moto-zenith-huy-namur-le-condroz/",
                    "registration_label": "S’inscrire",
                    
                },
                {
                    "title": "Zone Rouge La Louvière — Région du Centre",
                    "dates": "12/04/2026",
                    "price": "Gratuit",
                    "primary_url": "https://pulsion-inscription.com/balades-1-jour/lien/zone-rouge/",
                    "primary_label": "Voir la balade",
                    "registration_url": "https://pulsion-inscription.com/balades-1-jour/lien/zone-rouge/",
                    "registration_label": "S’inscrire",
                    
                },
                {
                    "title": "Zone Rouge Fosses-la-Ville — Le Namurois",
                    "dates": "19/04/2026",
                    "price": "Gratuit",
                    "primary_url": "https://pulsion-inscription.com/balades-1-jour/lien/zone-rouge/",
                    "primary_label": "Voir la balade",
                    "registration_url": "https://pulsion-inscription.com/balades-1-jour/lien/zone-rouge/",
                    "registration_label": "S’inscrire",
                    
                },
                {
                    "title": "Zone Rouge Andenne — Condroz / Ardennes",
                    "dates": "26/04/2026",
                    "price": "Gratuit",
                    "primary_url": "https://pulsion-inscription.com/balades-1-jour/lien/zone-rouge/",
                    "primary_label": "Voir la balade",
                    "registration_url": "https://pulsion-inscription.com/balades-1-jour/lien/zone-rouge/",
                    "registration_label": "S’inscrire",
                    
                },
                {
                    "title": "Pulsion Horizon — Hannut / Condroz",
                    "dates": "09/05/2026",
                    "price": "Gratuit",
                    "primary_url": "https://pulsion-inscription.com/balades-1-jour/",
                    "primary_label": "Voir la balade",
                    "registration_url": "https://pulsion-inscription.com/balades-1-jour/",
                    "registration_label": "S’inscrire",
                    
                },
                {
                    "title": "Ducati Sambreville — Namurois / Ardennes",
                    "dates": "23/05/2026",
                    "price": "Gratuit",
                    "primary_url": "https://pulsion-inscription.com/balades-1-jour/lien/ducati-sambreville-le-namurois/",
                    "primary_label": "Voir la balade",
                    "registration_url": "https://pulsion-inscription.com/balades-1-jour/lien/ducati-sambreville-le-namurois/",
                    "registration_label": "S’inscrire",
                    
                },
                {
                    "title": "JL Sélection Neufchâteau — Ardennes",
                    "dates": "30/05/2026",
                    "price": "Gratuit",
                    "primary_url": "https://pulsion-inscription.com/balades-1-jour/lien/jl-selection-neufchateau-ardennes/",
                    "primary_label": "Voir la balade",
                    "registration_url": "https://pulsion-inscription.com/balades-1-jour/lien/jl-selection-neufchateau-ardennes/",
                    "registration_label": "S’inscrire",
                    
                },
                {
                    "title": "Moto Casu Mons — Vers l’Eau d’Heure",
                    "dates": "06/06/2026",
                    "price": "Gratuit",
                    "primary_url": "https://pulsion-inscription.com/balades-1-jour/lien/moto-casu-mons-vers-leaux-dheure/",
                    "primary_label": "Voir la balade",
                    "registration_url": "https://pulsion-inscription.com/balades-1-jour/lien/moto-casu-mons-vers-leaux-dheure/",
                    "registration_label": "S’inscrire",
                    
                },
                {
                    "title": "Harley Liège — Le Liégeois",
                    "dates": "13/06/2026",
                    "price": "Gratuit",
                    "primary_url": "https://pulsion-inscription.com/balades-1-jour/lien/harley-liege-le-liegeois/",
                    "primary_label": "Voir la balade",
                    "registration_url": "https://pulsion-inscription.com/balades-1-jour/lien/harley-liege-le-liegeois/",
                    "registration_label": "S’inscrire",
                    
                },
            ],
            "links": [
                {
                    "label": "Toutes les balades",
                    "href": "https://pulsion-inscription.com/balades-1-jour/",
                },
            ],
        },

        {
            "slug": "grands-voyages",
            "title": "Grands voyages & destinations iconiques",
            "kicker": "Évasion premium",
            "description": "Les grandes expériences internationales et les voyages emblématiques de la saison.",
            "items": [
                {
                    "title": "USA en Harley",
                    "dates": "15/04 → 26/04 ou jusqu’au 01/05",
                    "duration": "12 ou 17 jours",
                    "price": "4 490 € (12 jours) · 6 900 € (17 jours)",
                    "primary_url": "https://pulsionhorizon.com/usa",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "Demander l’inscription",
                    "links": [
                        {"label": "Page détaillée", "href": "https://pulsionhorizon.com/usa"},
                        {"label": "Playlist 2024", "href": "https://youtube.com/playlist?list=PLdMDxuSlIsrvRreSOAEgq9vWwwoJUzh-h&si=s6jcMq4lud0D-V6c"},
                    ],
                },
                {
                    "title": "Laos",
                    "dates": "22/11 → 05/12",
                    "duration": "14 jours",
                    "price": "2 950 €",
                    "primary_url": "https://pulsionhorizon.com/lelaos",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "Demander l’inscription",
                    "links": [
                        {"label": "Page détaillée", "href": "https://pulsionhorizon.com/lelaos"},
                        {"label": "Vidéo", "href": "https://youtu.be/JBhY8BF7emw?si=H6SnVk2Kq0mHpNF8"},
                        {"label": "Playlist Laos 2025 — 1", "href": "https://youtube.com/playlist?list=PLdMDxuSlIsrtclR1jnlcnbJsAGFymxNPg&si=lcV_fv-JrSpDbYMn"},
                        {"label": "Playlist Laos 2025 — 2", "href": "https://youtube.com/playlist?list=PLdMDxuSlIsrttFwp5nB2_8Ey2ly8yD-Fs&si=c2QUX4chveaLhqNy"},
                        {"label": "Épisode 3", "href": "https://youtu.be/mRtr112kHYs?si=0G6NwliKUAEEYjcw"},
                    ],
                },
            ],
        },

        {
            "slug": "europe-premier-semestre",
            "title": "Europe — premier semestre",
            "kicker": "Printemps & début d’été",
            "description": "Les circuits européens du premier semestre, regroupés pour une lecture plus claire.",
            "items": [
                {
                    "title": "Forêt Noire",
                    "dates": "28/04 → 01/05 ou 02/05",
                    "duration": "4 ou 5 jours",
                    "price": "495 €",
                    "primary_url": "https://pulsionhorizon.com/normandie-bretagne-2026-/-foret-noire-2026",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [{"label": "Page détaillée", "href": "https://pulsionhorizon.com/normandie-bretagne-2026-/-foret-noire-2026"}],
                },
                {
                    "title": "Le Morvan",
                    "dates": "02/05 → 07/05",
                    "duration": "5 ou 6 jours",
                    "price": "520 €",
                    "primary_url": "https://pulsionhorizon.com/le-morvan",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [{"label": "Page détaillée", "href": "https://pulsionhorizon.com/le-morvan"}],
                },
                {
                    "title": "Luxembourg / Eifel",
                    "dates": "09/05 → 10/05",
                    "duration": "2 jours",
                    "price": "119 €",
                    "primary_url": "https://pulsionhorizon.com/luxembourg-eifel",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [{"label": "Page détaillée", "href": "https://pulsionhorizon.com/luxembourg-eifel"}],
                },
                {
                    "title": "Sardaigne",
                    "dates": "06/05 ou 07/05 → 17/05 ou 18/05",
                    "duration": "11 ou 13 jours",
                    "price": "1 230 €",
                    "primary_url": "https://pulsionhorizon.com/lasardaigne",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [
                        {"label": "Page détaillée", "href": "https://pulsionhorizon.com/lasardaigne"},
                        {"label": "Playlist 2023", "href": "https://www.youtube.com/playlist?list=PLdMDxuSlIsrsX4-o5ZCZLDGm24-qjv4l2"},
                        {"label": "Reportage 2022 — épisode 1", "href": "https://youtu.be/3Bkc--8wibE"},
                        {"label": "Reportage 2022 — épisode 2", "href": "https://youtu.be/QS_6jUSte2Y"},
                    ],
                },
                {
                    "title": "Corse I",
                    "dates": "18/05 ou 19/05 → 29/05 ou 30/05",
                    "duration": "11 ou 13 jours",
                    "price": "1 035 €",
                    "primary_url": "https://pulsionhorizon.com/la-corse",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [{"label": "Page détaillée", "href": "https://pulsionhorizon.com/la-corse"}],
                },
                {
                    "title": "Jura",
                    "dates": "21/05 → 25/05 ou 26/05",
                    "duration": "5 ou 6 jours",
                    "price": "590 €",
                    "primary_url": "https://pulsionhorizon.com/le-jura",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [
                        {"label": "Page détaillée", "href": "https://pulsionhorizon.com/le-jura"},
                        {"label": "Playlist", "href": "https://www.youtube.com/watch?v=bCrqoGDP7_4&list=PLdMDxuSlIsrt2-XsbWV3KImbHalHc8vFw&pp=gAQBiAQB"},
                    ],
                },
                {
                    "title": "Corse II",
                    "dates": "28/05 ou 29/05 → 08/06 ou 09/06",
                    "duration": "11 ou 13 jours",
                    "price": "1 035 €",
                    "primary_url": "https://pulsionhorizon.com/la-corse",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [
                        {"label": "Page détaillée", "href": "https://pulsionhorizon.com/la-corse"},
                        {"label": "Playlist Corse 2023", "href": "https://youtube.com/playlist?list=PLdMDxuSlIsrtB1Mu0jR47SpxJgbNTbZx3&si=NXFVeonGvJpRcXwz"},
                        {"label": "Playlist Corse 2025", "href": "https://youtube.com/playlist?list=PLdMDxuSlIsrssgrFywiJlSqS1nxuB8B3o&si=Lt-ydeuC5cL33jze"},
                    ],
                },
                {
                    "title": "Lorraine et Vosges",
                    "dates": "16/05 → 18/05 ou 19/05",
                    "duration": "3 jours",
                    "price": "240 €",
                    "primary_url": "https://pulsionhorizon.com/lorraine-vosges-16185-3-jours-230-",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [{"label": "Page détaillée", "href": "https://pulsionhorizon.com/lorraine-vosges-16185-3-jours-230-"}],
                },
                {
                    "title": "Toscane — Cinque Terre — Lac de Garde",
                    "dates": "27/05 → 05/06",
                    "duration": "8 ou 10 jours",
                    "price": "1 250 €",
                    "primary_url": "https://pulsionhorizon.com/toscane",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [{"label": "Page détaillée", "href": "https://pulsionhorizon.com/toscane"}],
                },
                {
                    "title": "Normandie — Bretagne",
                    "dates": "06/06 → 10/06",
                    "duration": "4 ou 5 jours",
                    "price": "495 €",
                    "primary_url": "https://pulsionhorizon.com/normandie-bretagne",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [{"label": "Page détaillée", "href": "https://pulsionhorizon.com/normandie-bretagne"}],
                },
                {
                    "title": "Dolomites",
                    "dates": "11/06 → 19/06",
                    "duration": "8 ou 9 jours",
                    "price": "1 190 €",
                    "primary_url": "https://pulsionhorizon.com/dolomites",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [
                        {"label": "Page détaillée", "href": "https://pulsionhorizon.com/dolomites"},
                        {"label": "Playlist", "href": "https://www.youtube.com/watch?v=-2h6ZFdGNlE&list=PLdMDxuSlIsrsVqcK_Q3sNJ3l3QWh8ggTU&pp=gAQBiAQB"},
                        {"label": "Playlist 2025", "href": "https://youtube.com/playlist?list=PLdMDxuSlIsrt5ptnzvbHiU_RWroUsP2F5&si=8S45kDVqxAdnVxgx"},
                    ],
                },
                {
                    "title": "Pyrénées",
                    "dates": "11/06 ou 20/06",
                    "duration": "9 ou 10 jours",
                    "price": "1 340 €",
                    "primary_url": "https://pulsionhorizon.com/pyrenees",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [{"label": "Page détaillée", "href": "https://pulsionhorizon.com/pyrenees"}],
                },
                {
                    "title": "Alsace",
                    "dates": "17/06 → 21/06",
                    "duration": "3, 4 ou 5 jours",
                    "price": "340 €",
                    "primary_url": "https://pulsionhorizon.com/alsace",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [{"label": "Page détaillée", "href": "https://pulsionhorizon.com/alsace"}],
                },
                {
                    "title": "Écosse",
                    "dates": "21/06 → 29/06",
                    "duration": "9 jours",
                    "price": "1 990 €",
                    "primary_url": "https://pulsionhorizon.com/ecosses",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [
                        {"label": "Page détaillée", "href": "https://pulsionhorizon.com/ecosses"},
                        {"label": "Playlist", "href": "https://www.youtube.com/watch?v=Q3J-oxwZjMk&list=PLdMDxuSlIsrugpwGQFGlVka2MfxpM1fmu&pp=gAQBiAQB"},
                    ],
                },
                {
                    "title": "Corse III",
                    "dates": "29/06 ou 30/06 → 10/07 ou 11/07",
                    "duration": "11 ou 13 jours",
                    "price": "1 035 €",
                    "primary_url": "https://pulsionhorizon.com/la-corse",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [
                        {"label": "Page détaillée", "href": "https://pulsionhorizon.com/la-corse"},
                        {"label": "Playlist Corse 2023", "href": "https://youtube.com/playlist?list=PLdMDxuSlIsrtB1Mu0jR47SpxJgbNTbZx3&si=NXFVeonGvJpRcXwz"},
                        {"label": "Playlist Corse 2025", "href": "https://youtube.com/playlist?list=PLdMDxuSlIsrssgrFywiJlSqS1nxuB8B3o&si=Lt-ydeuC5cL33jze"},
                    ],
                },
            ],
        },

        {
            "slug": "europe-deuxieme-semestre",
            "title": "Europe — deuxième semestre",
            "kicker": "Fin d’été & automne",
            "description": "Les circuits européens du second semestre, regroupés sur une seule section lisible.",
            "items": [
                {
                    "title": "Corse IV",
                    "dates": "26/08 ou 27/08 → 06/09 ou 07/09",
                    "duration": "11 ou 13 jours",
                    "price": "1 035 €",
                    "primary_url": "https://pulsionhorizon.com/la-corse",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [
                        {"label": "Page détaillée", "href": "https://pulsionhorizon.com/la-corse"},
                        {"label": "Playlist Corse 2023", "href": "https://youtube.com/playlist?list=PLdMDxuSlIsrtB1Mu0jR47SpxJgbNTbZx3&si=NXFVeonGvJpRcXwz"},
                        {"label": "Playlist Corse 2025", "href": "https://youtube.com/playlist?list=PLdMDxuSlIsrssgrFywiJlSqS1nxuB8B3o&si=Lt-ydeuC5cL33jze"},
                    ],
                },
                {
                    "title": "Alpes du Sud",
                    "dates": "28/08 ou 29/08 → 05/09",
                    "duration": "9 jours",
                    "price": "1 290 €",
                    "primary_url": "https://pulsionhorizon.com/les-alpes-du-sud-du-278-au-49",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [
                        {"label": "Page détaillée", "href": "https://pulsionhorizon.com/les-alpes-du-sud-du-278-au-49"},
                        {"label": "Playlist 2023", "href": "https://www.youtube.com/watch?v=SnjDultz3aU&list=PLdMDxuSlIsrsF3ZZ_QZ9o1omypoAJQ9D5"},
                    ],
                },
                {
                    "title": "Croatie",
                    "dates": "05/09 → 18/09 ou 19/09",
                    "duration": "12 ou 14 jours",
                    "price": "1 390 €",
                    "primary_url": "https://pulsionhorizon.com/la-croatie",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [
                        {"label": "Page détaillée", "href": "https://pulsionhorizon.com/la-croatie"},
                        {"label": "Playlist 2024", "href": "https://youtube.com/playlist?list=PL52AtAN9nw2N3SMrc75YGh5vEo7u6SCpU&si=7ZgPdwM2fR9TtC8n"},
                        {"label": "Playlist 2023", "href": "https://www.youtube.com/playlist?list=PLdMDxuSlIsrvC28U-9T14AnaJLn5so2UR"},
                        {"label": "Reportage 2025", "href": "https://www.albertinomoto.be/tous-les-voyages-%C3%A0-moto/croatie-2025/"},
                    ],
                },
                {
                    "title": "Dolomites II",
                    "dates": "05/09 → 13/09",
                    "duration": "8 ou 9 jours",
                    "price": "1 190 €",
                    "primary_url": "https://pulsionhorizon.com/dolomites",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [{"label": "Page détaillée", "href": "https://pulsionhorizon.com/dolomites"}],
                },
                {
                    "title": "Visite de l’usine Guzzi à Mandello",
                    "dates": "10/09 ou 11/09 → 15/09",
                    "duration": "5 ou 6 jours",
                    "price": "690 €",
                    "primary_url": "https://pulsionhorizon.com/circuit-vers-mandello",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "note": "Possibilité de combiner Dolomites II et Mandello pour +220 €.",
                    "links": [{"label": "Page détaillée", "href": "https://pulsionhorizon.com/circuit-vers-mandello"}],
                },
                {
                    "title": "Alsace II",
                    "dates": "11/09 ou 15/09",
                    "duration": "3 ou 5 jours",
                    "price": "340 €",
                    "primary_url": "https://pulsionhorizon.com/alsace",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [{"label": "Page détaillée", "href": "https://pulsionhorizon.com/alsace"}],
                },
                {
                    "title": "Corse V",
                    "dates": "14/09 ou 15/09 → 26/09 ou 27/09",
                    "duration": "11 ou 13 jours",
                    "price": "1 035 €",
                    "primary_url": "https://pulsionhorizon.com/la-corse",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "S’inscrire",
                    "links": [
                        {"label": "Page détaillée", "href": "https://pulsionhorizon.com/la-corse"},
                        {"label": "Playlist Corse 2023", "href": "https://youtube.com/playlist?list=PLdMDxuSlIsrtB1Mu0jR47SpxJgbNTbZx3&si=NXFVeonGvJpRcXwz"},
                        {"label": "Playlist Corse 2025", "href": "https://youtube.com/playlist?list=PLdMDxuSlIsrssgrFywiJlSqS1nxuB8B3o&si=Lt-ydeuC5cL33jze"},
                    ],
                },
            ],
        },

        {
            "slug": "raids-afrique",
            "title": "Raids Maroc & Afrique",
            "kicker": "Aventure & engagement",
            "description": "Les voyages plus engagés, mixtes route/piste, et les grandes expériences raid.",
            "items": [
                {
                    "title": "Raid Maroc — route ou piste",
                    "dates": "03/10 → 19/10",
                    "duration": "17 jours",
                    "price": "2 350 €",
                    "primary_url": "https://pulsionhorizon.com/raid-sud-maroc-2026",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "Demander l’inscription",
                    "note": "Accessible aussi pour Harley selon la formule.",
                    "links": [{"label": "Page détaillée", "href": "https://pulsionhorizon.com/raid-sud-maroc-2026"}],
                },
                {
                    "title": "Raid GS ou Ténéré de location au Maroc",
                    "dates": "08/10 → 17/10",
                    "duration": "10 jours",
                    "price": "1 950 €",
                    "primary_url": "https://pulsionhorizon.com/raidgsmaroc",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "Demander l’inscription",
                    "links": [
                        {"label": "Page détaillée", "href": "https://pulsionhorizon.com/raidgsmaroc"},
                        {"label": "Programme PDF", "href": "https://static1.squarespace.com/static/55ba69cae4b00bb94e12e391/t/67b704b16b45d8310ea32f73/1740047543203/Programme+Maroc+en+GS+Tour+Dec+25+-+Avril+26.pdf"},
                        {"label": "Playlist octobre 2025", "href": "https://youtube.com/playlist?list=PLdMDxuSlIsruJHNO3Pv3n4IyYDWUa8O9S&si=6a45wj40geKoORAX"},
                    ],
                },
                {
                    "title": "Raid Ténéré de location — off road",
                    "dates": "07/10 → 17/10",
                    "duration": "11 jours",
                    "price": "Programme sur demande",
                    "registration_url": inscription_url_default,
                    "registration_label": "Demander des informations",
                    "note": "Réservé aux pilotes ayant une très bonne expérience en tout terrain.",
                    "links": [],
                },
                {
                    "title": "Raid Bruxelles / Dakar",
                    "dates": "03/10 → 25/10",
                    "duration": "24 jours",
                    "price": "4 750 €",
                    "primary_url": "https://pulsionhorizon.com/raid-bruxelles-dakar",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "Demander l’inscription",
                    "note": "Formule 100% route ou mixte route/piste.",
                    "links": [
                        {"label": "Page détaillée", "href": "https://pulsionhorizon.com/raid-bruxelles-dakar"},
                        {"label": "Playlist 2023", "href": "https://www.youtube.com/playlist?list=PLdMDxuSlIsrvZ5QeRNFsaW5II4qNcBga8"},
                    ],
                },
            ],
        },

        {
            "slug": "senegal",
            "title": "Découverte Sénégal — moto & 4x4",
            "kicker": "Authentique & dépaysant",
            "description": "Les expériences Sénégal en 4x4 ou à moto, avec une vraie dimension découverte, safari et détente.",
            "items": [
                {
                    "title": "Circuit Sénégal 4x4",
                    "dates": "8 jours",
                    "duration": "Mixte découverte / safari / détente",
                    "price": "À partir de 339 €",
                    "primary_url": "https://pulsionhorizon.com/circuit-4x4",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "Demander l’inscription",
                    "links": [
                        {"label": "Page détaillée", "href": "https://pulsionhorizon.com/circuit-4x4"},
                        {"label": "Reportage", "href": "https://www.youtube.com/watch?v=AwOpUqKkL7k&list=PLdMDxuSlIsrufx6QPnG2horXLzsQTyqxW&pp=gAQBiAQB"},
                        {"label": "Playlist", "href": "https://www.youtube.com/watch?v=AwOpUqKkL7k&list=PLdMDxuSlIsrufx6QPnG2horXLzsQTyqxW"},
                    ],
                },
                {
                    "title": "Circuit Yam XT 600",
                    "dates": "10 jours",
                    "duration": "À partir de 2 pilotes — maximum 10",
                    "price": "1 190 €",
                    "primary_url": "https://pulsionhorizon.com/circuit-moto-xt-600",
                    "primary_label": "Voir le circuit",
                    "registration_url": inscription_url_default,
                    "registration_label": "Demander l’inscription",
                    "note": (
                        "Possibilité d’arriver 2 jours plus tôt pour une initiation à la conduite "
                        "dans le sable au guidon de KLX 450."
                    ),
                    "links": [
                        {"label": "Page détaillée", "href": "https://pulsionhorizon.com/circuit-moto-xt-600"},
                        {"label": "Épopée au Sénégal", "href": "https://youtu.be/TKnj8TPg5Jo?feature=shared"},
                        {"label": "Playlist XT 600", "href": "https://www.youtube.com/watch?v=9cafohB7oQE&list=PLdMDxuSlIsrtHpzIjbspNVcX_GAYpyNXG&pp=gAQBiAQB"},
                    ],
                },
            ],
        },
    ]

    total_items = sum(len(section.get("items", [])) for section in sections)

    return render(
        request,
        "circuitMoto/programme.html",
        {
            "programme_title": programme_title,
            "programme_intro": programme_intro,
            "programme_notice": programme_notice,
            "sections": sections,
            "total_items": total_items,
        },
    )
