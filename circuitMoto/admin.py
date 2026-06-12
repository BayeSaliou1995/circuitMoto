# admin.py
from django.urls import reverse
from django.contrib import admin, messages # type: ignore
from django.db.models import Count, Q, Sum # type: ignore
from django.utils import timezone # type: ignore
from django.utils.html import format_html # type: ignore
from django.conf import settings # type: ignore
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q
from modeltranslation.admin import TabbedTranslationAdmin, TranslationTabularInline
from .translation_utils import auto_translate_instance


from .models import (
    # Référentiels & personnes
    Personne, ContactUrgence, InfosMedicales, Moto,
    # Circuits
    Circuit, OptionCircuit,
    # Inscriptions
    Inscription, SelectionOption,
    # Assurance / Décharge / Documents
    Assurance, DechargeSignee, Document,
    # Paiements hors système
    Paiement,
    # Rappels / Audit
    JournalRappel, JournalAudit,
    # Choix (si besoin pour filtres/affichages)
    StatutCircuit, StatutInscription, StatutDocument, LibellePaiement, StatutPaiement,
    # Helper
    initialiser_plan_paiement_par_defaut,
    # Newsletter
    NewsletterSubscriber,
    # Password history
    PasswordHistory,
    Programme2027Circuit, Programme2027Interest, Programme2027Selection
)

# Branding Admin
admin.site.site_header = "Pulison Horizon — CircuitMoto"   # bandeau en haut
admin.site.site_title = "CircuitMoto • Admin"                    # titre de l'onglet navigateur
admin.site.index_title = "Tableau de bord"                       # titre de la page d'accueil admin
admin.site.site_url = "/"                                        # lien “Voir le site” (en haut à gauche)


# ─────────────────────────────────────────────────────────────
# Inlines Personne
# ─────────────────────────────────────────────────────────────

class ContactUrgenceInline(admin.TabularInline):
    model = ContactUrgence
    extra = 0
    fields = ("nom", "lien_parente", "telephone")
    verbose_name = "Contact d’urgence"
    verbose_name_plural = "Contacts d’urgence"

class InfosMedicalesInline(admin.StackedInline):
    model = InfosMedicales
    extra = 0
    can_delete = True
    verbose_name = "Informations médicales"
    verbose_name_plural = "Informations médicales"

class MotoInline(admin.TabularInline):
    model = Moto
    extra = 0
    fields = ("marque", "modele", "immatriculation")
    verbose_name = "Moto"
    verbose_name_plural = "Motos"

# == AJOUT : outils ==
def _doc_changelist_url():
    return reverse(f"admin:{Document._meta.app_label}_{Document._meta.model_name}_changelist")

class _BaseInscriptionInline(admin.TabularInline):
    model = Inscription
    extra = 0
    show_change_link = True
    fields = ("circuit", "statut", "docs_badges", "gerer_docs")
    readonly_fields = ("docs_badges", "gerer_docs")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("circuit").annotate(
            docs_total=Count("documents"),
            docs_att=Count("documents", filter=Q(documents__statut=StatutDocument.EN_ATTENTE)),
            docs_val=Count("documents", filter=Q(documents__statut=StatutDocument.VALIDE)),
            docs_ref=Count("documents", filter=Q(documents__statut=StatutDocument.REFUSE)),
        )

    def docs_badges(self, obj):
        t = getattr(obj, "docs_total", 0)
        att = getattr(obj, "docs_att", 0)
        val = getattr(obj, "docs_val", 0)
        ref = getattr(obj, "docs_ref", 0)
        return format_html(
            '<span style="background:#e5e7eb;border-radius:10px;padding:2px 6px;margin-right:.25rem;">{} doc(s)</span>'
            '<span style="background:#f59e0b;color:#111;border-radius:10px;padding:2px 6px;margin-right:.25rem;">Att: {}</span>'
            '<span style="background:#10b981;color:#fff;border-radius:10px;padding:2px 6px;margin-right:.25rem;">OK: {}</span>'
            '<span style="background:#ef4444;color:#fff;border-radius:10px;padding:2px 6px;">Ref: {}</span>',
            t, att, val, ref
        )
    docs_badges.short_description = "Documents"

    def gerer_docs(self, obj):
        url = _doc_changelist_url() + f"?inscription__id__exact={obj.pk}"
        return format_html('<a class="button" href="{}">Gérer</a>', url)
    gerer_docs.short_description = "Actions"


class InscriptionsPiloteInline(_BaseInscriptionInline):
    fk_name = "pilote"


class InscriptionsPassagerInline(_BaseInscriptionInline):
    fk_name = "passager"


@admin.register(Personne)
class PersonneAdmin(admin.ModelAdmin):
    list_display = ("nom", "prenom", "email", "telephone", "localite", "pays", "cree_le")
    search_fields = ("nom", "prenom", "email", "telephone", "numero_carte_identite", "localite", "pays")
    list_filter = ("pays",)
    readonly_fields = ("cree_le", "modifie_le", "documents_resume")
    inlines = [InfosMedicalesInline, ContactUrgenceInline, MotoInline,
               InscriptionsPiloteInline, InscriptionsPassagerInline]
    fieldsets = (
        ("Identité", {"fields": (("prenom", "nom"), "email", "telephone")}),
        ("Adresse", {"fields": ("adresse", ("code_postal", "localite"), "pays")}),
        ("Infos", {"fields": ("date_naissance", "numero_carte_identite")}),
        ("Documents (résumé)", {"fields": ("documents_resume",)}),
        ("Métadonnées", {"fields": ("cree_le", "modifie_le")}),
    )
    ordering = ("nom", "prenom")

    def documents_resume(self, obj):
        qs = Document.objects.filter(Q(inscription__pilote=obj) | Q(inscription__passager=obj))
        tot = qs.count()
        att = qs.filter(statut=StatutDocument.EN_ATTENTE).count()
        val = qs.filter(statut=StatutDocument.VALIDE).count()
        ref = qs.filter(statut=StatutDocument.REFUSE).count()
        url = _doc_changelist_url() + f"?personne={obj.pk}"
        return format_html(
            '<div>'
            '<span style="background:#e5e7eb;border-radius:10px;padding:2px 8px;margin-right:.25rem;">{} doc(s)</span>'
            '<span style="background:#f59e0b;color:#111;border-radius:10px;padding:2px 8px;margin-right:.25rem;">Att: {}</span>'
            '<span style="background:#10b981;color:#fff;border-radius:10px;padding:2px 8px;margin-right:.25rem;">OK: {}</span>'
            '<span style="background:#ef4444;color:#fff;border-radius:10px;padding:2px 8px;margin-right:.75rem;">Ref: {}</span>'
            '<a class="button" href="{}">Gérer tous les documents</a>'
            '</div>',
            tot, att, val, ref, url
        )


# ─────────────────────────────────────────────────────────────
# Inlines Circuit
# ─────────────────────────────────────────────────────────────

class OptionCircuitInline(TranslationTabularInline):  # ← ICI
    model = OptionCircuit
    extra = 0
    fields = (
        "code", "intitule", "categorie",
        "prix_unitaire", "facture_par_personne",
        "quantite_variable", "quantite_min", "quantite_max",
        "description",
    )
    show_change_link = True

AUTO_FIELDS_CIRCUIT = (
    "nom", "description", "infos_rdv",
    "programme", "kilometrages",
    "prix_comprend", "prix_ne_comprend_pas",
    "echeancier_texte",
)

@admin.register(Circuit)
class CircuitAdmin(TabbedTranslationAdmin):
    list_display = ("nom", "code", "periode", "capacite",
                    "nb_inscriptions", "statut_badge", "devise", "cree_le")
    list_filter = ("statut", "devise", ("date_debut", admin.DateFieldListFilter))
    search_fields = ("nom", "code", "description", "infos_rdv")
    date_hierarchy = "date_debut"
    inlines = [OptionCircuitInline]
    readonly_fields = ("cree_le", "modifie_le")
    fieldsets = (
        ("Identification", {"fields": (("nom", "code"), "statut")}),
        ("Période", {"fields": (("date_debut", "date_fin"),)}),
        ("Capacité & devise", {"fields": (("capacite", "devise"),)}),
        ("Tarifs de référence", {"fields": (("prix_pilote_unitaire", "prix_passager_unitaire"),)}),
        ("Paramètres d’option", {"fields": ("delai_option_jours",)}),
        ("Contenus", {"fields": ("description", "infos_rdv")}),
        ("Carte interactive", {"fields": (
            "itineraire_active",
            "itineraire_points",
            "itineraire_google_maps_url",
            "itineraire_embed_url",
            "itineraire_street_view_url",
        )}),
        ("Métadonnées", {"fields": ("cree_le", "modifie_le")}),
    )

    # --- IMPORTANT : rétablir ces méthodes ---

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # annote nb = nombre d’inscriptions non annulées
        return qs.annotate(
            nb=Count("inscriptions", filter=~Q(inscriptions__statut=StatutInscription.ANNULEE))
        )

    def nb_inscriptions(self, obj):
        return getattr(obj, "nb", 0)
    nb_inscriptions.short_description = "Inscriptions"
    nb_inscriptions.admin_order_field = "nb"

    def periode(self, obj):
        if obj.date_debut and obj.date_fin:
            return f"{obj.date_debut:%d/%m/%Y} → {obj.date_fin:%d/%m/%Y}"
        if obj.date_debut:
            return f"À partir du {obj.date_debut:%d/%m/%Y}"
        return "—"
    periode.short_description = "Période"
    periode.admin_order_field = "date_debut"

    def statut_badge(self, obj):
        color = {
            "BROUILLON": "#999",
            "PUBLIE": "#15803d",
            "ARCHIVE": "#6b7280",
        }.get(obj.statut, "#374151")
        return format_html(
            '<span style="padding:2px 8px;border-radius:10px;background:{};color:#fff;">{}</span>',
            color, obj.get_statut_display()
        )
    statut_badge.short_description = "Statut"

    def save_model(self, request, obj, form, change):
        # Auto-traduction FR→EN si besoin
        if auto_translate_instance(obj, AUTO_FIELDS_CIRCUIT):
            pass  # les champs EN ont été posés en mémoire
        super().save_model(request, obj, form, change)

    @admin.action(description="Auto-traduire FR → EN (champs texte)")
    def action_autotranslate(self, request, queryset):
        n = 0
        for c in queryset:
            if auto_translate_instance(c, AUTO_FIELDS_CIRCUIT):
                c.save()
                n += 1
        self.message_user(request, f"{n} circuit(s) mis à jour.")

    actions = ("action_autotranslate",)


@admin.action(description="Publier les circuits sélectionnés")
def action_publier_circuits(modeladmin, request, queryset):
    nb = queryset.update(statut=StatutCircuit.PUBLIE)
    messages.success(request, f"{nb} circuit(s) publié(s).")

@admin.action(description="Archiver les circuits sélectionnés")
def action_archiver_circuits(modeladmin, request, queryset):
    nb = queryset.update(statut=StatutCircuit.ARCHIVE)
    messages.success(request, f"{nb} circuit(s) archivé(s).")

# ─────────────────────────────────────────────────────────────
# Inlines Inscription
# ─────────────────────────────────────────────────────────────

class SelectionOptionInline(admin.TabularInline):
    model = SelectionOption
    extra = 0
    fields = ("option", "quantite", "prix_unitaire_fige", "pour_passager")
    autocomplete_fields = ("option",)

class AssuranceInline(admin.StackedInline):
    model = Assurance
    extra = 0

class DechargeSigneeInline(admin.StackedInline):
    model = DechargeSignee
    extra = 0
    readonly_fields = ("signee_le", "adresse_ip", "preuve_pdf")

class DocumentInline(admin.TabularInline):
    model = Document
    extra = 0
    fields = ("type_document", "fichier", "statut", "verifie_par", "verifie_le", "note")
    readonly_fields = ("verifie_le",)
    autocomplete_fields = ("verifie_par",)

class PaiementInline(admin.TabularInline):
    model = Paiement
    extra = 0
    fields = ("libelle", "echeance_le", "montant_du", "montant_encaisse", "encaisse_le", "methode", "reference", "statut")
    readonly_fields = ("statut",)

# ─────────────────────────────────────────────────────────────
# Actions Inscription
# ─────────────────────────────────────────────────────────────

@admin.action(description="Verrouiller les inscriptions (fige les totaux)")
def action_verrouiller_inscriptions(modeladmin, request, queryset):
    ok, ko = 0, 0
    for ins in queryset:
        try:
            ins.verrouiller()
            ok += 1
        except Exception as e:
            ko += 1
    if ok:
        messages.success(request, f"{ok} inscription(s) verrouillée(s).")
    if ko:
        messages.warning(request, f"{ko} inscription(s) non verrouillée(s) (voir journaux serveur).")

@admin.action(description="Générer le plan d’échéances (Acompte1/Acompte2/Solde)")
def action_generer_plan_echeances(modeladmin, request, queryset):
    c = 0
    for ins in queryset:
        try:
            initialiser_plan_paiement_par_defaut(ins)
            c += 1
        except Exception:
            pass
    messages.success(request, f"Plan d’échéances généré pour {c} inscription(s).")

@admin.register(Inscription)
class InscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "circuit", "participants", "statut_badge",
        "prix_base_aff", "options_aff", "total_calcule_aff",
        "option_expire_le", "verrouillee_le", "cree_le"
    )
    list_filter = ("statut", ("option_expire_le", admin.DateFieldListFilter), ("verrouillee_le", admin.DateFieldListFilter), "circuit")
    search_fields = (
        "circuit__nom", "circuit__code",
        "pilote__nom", "pilote__prenom", "pilote__email", "pilote__telephone",
        "passager__nom", "passager__prenom", "passager__email",
        "id_public",
    )
    date_hierarchy = "cree_le"
    readonly_fields = ("id_public", "sous_total_fige", "total_fige", "cree_le", "modifie_le")
    fieldsets = (
        ("Circuit & personnes", {"fields": ("circuit", ("pilote", "passager"))}),
        ("Devises & prix figés", {"fields": (("devise", "prix_pilote_unitaire", "prix_passager_unitaire"),)}),
        ("Statut & dates", {"fields": (("statut", "date_option", "option_expire_le"), "verrouillee_le")}),
        ("Totaux figés", {"fields": (("sous_total_fige", "total_fige"),)}),
        ("Notes", {"fields": ("notes",)}),
        ("Métadonnées", {"fields": ("id_public", "cree_par", "cree_le", "modifie_le")}),
    )
    inlines = [SelectionOptionInline, AssuranceInline, DechargeSigneeInline, DocumentInline, PaiementInline]
    autocomplete_fields = ("circuit", "pilote", "passager", "cree_par")
    actions = [action_verrouiller_inscriptions, action_generer_plan_echeances]
    ordering = ("-cree_le",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("circuit", "pilote", "passager").prefetch_related("selections_options__option")

    # Affichages
    def participants(self, obj):
        return f"{obj.pilote.nom_complet}" + (f" + {obj.passager.nom_complet}" if obj.passager_id else "")
    participants.short_description = "Participants"

    def statut_badge(self, obj):
        color = {
            "OPTION": "#1f2937",
            "VALIDE": "#2563eb",
            "ANNULEE": "#6b7280",
            "TERMINEE": "#047857",
        }.get(obj.statut, "#374151")
        return format_html('<span style="padding:2px 8px;border-radius:10px;background:{};color:#fff;">{}</span>',
                           color, obj.get_statut_display())
    statut_badge.short_description = "Statut"

    def prix_base_aff(self, obj):
        base = (obj.prix_pilote_unitaire or 0) + ((obj.prix_passager_unitaire or 0) if obj.passager_id else 0)
        return f"{base:,} {obj.devise}".replace(",", " ")
    prix_base_aff.short_description = "Prix de base"

    def options_aff(self, obj):
        total_opts = sum(s.prix_total() for s in obj.selections_options.all())
        return f"{total_opts:,} {obj.devise}".replace(",", " ")
    options_aff.short_description = "Options"

    def total_calcule_aff(self, obj):
        t = obj.total_attendu()
        return f"{t:,} {obj.devise}".replace(",", " ")
    total_calcule_aff.short_description = "Total calculé"

# ─────────────────────────────────────────────────────────────
# Documents
# ─────────────────────────────────────────────────────────────

@admin.action(description="Valider les documents sélectionnés")
def action_valider_documents(modeladmin, request, queryset):
    c = 0
    for doc in queryset:
        doc.valider(getattr(request, "user", None))
        c += 1
    messages.success(request, f"{c} document(s) validé(s).")

@admin.action(description="Refuser les documents sélectionnés")
def action_refuser_documents(modeladmin, request, queryset):
    c = 0
    for doc in queryset:
        doc.refuser("Refus via admin", getattr(request, "user", None))
        c += 1
    messages.success(request, f"{c} document(s) refusé(s).")

# Filtre URL-only : ?personne=<id>
class ParPersonneFilter(admin.SimpleListFilter):
    title = "Personne"
    parameter_name = "personne"
    def lookups(self, request, model_admin): return ()
    def queryset(self, request, queryset):
        pid = self.value()
        if pid:
            return queryset.filter(Q(inscription__pilote_id=pid) | Q(inscription__passager_id=pid))
        return queryset

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "circuit_col", "pilote_col", "passager_col",
        "type_document", "statut_colore",
        "verifie_par", "verifie_le", "fichier_lien", "cree_le",
    )
    list_filter = (
        "type_document", "statut",
        ("verifie_le", admin.DateFieldListFilter),
        "inscription__circuit",
        ParPersonneFilter,
    )
    search_fields = (
        "inscription__circuit__code", "inscription__circuit__nom",
        "inscription__pilote__nom", "inscription__pilote__prenom", "inscription__pilote__email",
        "inscription__passager__nom", "inscription__passager__prenom",
    )
    list_select_related = ("inscription__circuit", "inscription__pilote", "inscription__passager", "verifie_par")
    autocomplete_fields = ("inscription", "verifie_par")
    readonly_fields = ("verifie_le", "cree_le", "modifie_le")
    actions = [action_valider_documents, action_refuser_documents]
    ordering = ("-cree_le",)
    list_per_page = 50

    def circuit_col(self, obj): return obj.inscription.circuit
    circuit_col.short_description = "Circuit"

    def pilote_col(self, obj):
        p = obj.inscription.pilote
        return f"{p.prenom} {p.nom}"
    pilote_col.short_description = "Pilote"

    def passager_col(self, obj):
        if obj.inscription.passager_id:
            p = obj.inscription.passager
            return f"{p.prenom} {p.nom}"
        return "—"
    passager_col.short_description = "Passager"

    def fichier_lien(self, obj):
        if obj.fichier:
            return format_html('<a href="{}" target="_blank">Ouvrir</a>', obj.fichier.url)
        return "—"
    fichier_lien.short_description = "Fichier"

    def statut_colore(self, obj):
        color = {
            "EN_ATTENTE": "#92400e",
            "VALIDE": "#065f46",
            "REFUSE": "#991b1b",
        }.get(obj.statut, "#374151")
        return format_html('<b style="color:{};">{}</b>', color, obj.get_statut_display())
    statut_colore.short_description = "Statut"

# ─────────────────────────────────────────────────────────────
# Assurance & Décharge
# ─────────────────────────────────────────────────────────────

@admin.register(Assurance)
class AssuranceAdmin(admin.ModelAdmin):
    list_display = ("inscription", "type", "compagnie", "numero_police", "periode", "cree_le")
    list_filter = ("type",)
    search_fields = ("inscription__circuit__code", "compagnie", "numero_police")
    autocomplete_fields = ("inscription",)
    readonly_fields = ("cree_le", "modifie_le")

    def periode(self, obj):
        if obj.valide_du and obj.valide_au:
            return f"{obj.valide_du:%d/%m/%Y} → {obj.valide_au:%d/%m/%Y}"
        return "-"
    periode.short_description = "Période"

@admin.register(DechargeSignee)
class DechargeSigneeAdmin(admin.ModelAdmin):
    list_display = ("inscription", "version_texte", "nom_signataire", "email_signataire", "signee_le")
    search_fields = ("inscription__circuit__code", "nom_signataire", "email_signataire", "version_texte")
    autocomplete_fields = ("inscription",)
    readonly_fields = ("signee_le", "adresse_ip", "preuve_pdf", "cree_le", "modifie_le")
    fieldsets = (
        (None, {"fields": ("inscription", "version_texte")}),
        ("Signature", {"fields": ("nom_signataire", "email_signataire", "signee_le", "adresse_ip", "otp_4_derniers", "preuve_pdf")}),
        ("Métadonnées", {"fields": ("cree_le", "modifie_le")}),
    )

# ─────────────────────────────────────────────────────────────
# Paiements hors système
# ─────────────────────────────────────────────────────────────

@admin.action(description="Marquer PAYÉ (montant encaissé = montant dû, date = aujourd’hui)")
def action_marquer_paye(modeladmin, request, queryset):
    ajd = timezone.now().date()
    c = 0
    for p in queryset:
        p.montant_encaisse = p.montant_du
        p.encaisse_le = p.encaisse_le or ajd
        if not p.methode:
            p.methode = "ESPECES"
        p.save()
        c += 1
    messages.success(request, f"{c} paiement(s) marqué(s) comme PAYÉ(S).")

@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ("inscription", "libelle", "montant_du_aff", "montant_encaisse_aff", "echeance_le", "encaisse_le", "methode", "statut_badge")
    list_filter = ("libelle", "methode", "statut", ("echeance_le", admin.DateFieldListFilter), ("encaisse_le", admin.DateFieldListFilter))
    search_fields = (
        "inscription__circuit__code",
        "inscription__pilote__nom", "inscription__pilote__prenom",
        "reference",
    )
    autocomplete_fields = ("inscription",)
    readonly_fields = ("statut", "cree_le", "modifie_le")
    actions = [action_marquer_paye]
    ordering = ("-cree_le",)

    def montant_du_aff(self, obj):
        return f"{obj.montant_du:,}".replace(",", " ")
    montant_du_aff.short_description = "Montant attendu"

    def montant_encaisse_aff(self, obj):
        return f"{obj.montant_encaisse:,}".replace(",", " ")
    montant_encaisse_aff.short_description = "Montant encaissé"

    def statut_badge(self, obj):
        color = {
            "A_PAYER": "#92400e",
            "PARTIEL": "#2563eb",
            "PAYE": "#065f46",
            "ANNULE": "#6b7280",
        }.get(obj.statut, "#374151")
        return format_html('<span style="padding:2px 8px;border-radius:10px;background:{};color:#fff;">{}</span>',
                           color, obj.get_statut_display())
    statut_badge.short_description = "Statut"

# ─────────────────────────────────────────────────────────────
# Journaux
# ─────────────────────────────────────────────────────────────

@admin.register(JournalRappel)
class JournalRappelAdmin(admin.ModelAdmin):
    list_display = ("inscription", "type_rappel", "canal", "destinataire", "envoye_le")
    list_filter = ("type_rappel", "canal", ("envoye_le", admin.DateFieldListFilter))
    search_fields = ("inscription__circuit__code", "destinataire")
    autocomplete_fields = ("inscription",)
    readonly_fields = ("cree_le", "modifie_le")

@admin.register(JournalAudit)
class JournalAuditAdmin(admin.ModelAdmin):
    list_display = ("inscription", "acteur", "action", "cree_le")
    search_fields = ("inscription__circuit__code", "action", "acteur__username", "acteur__first_name", "acteur__last_name")
    list_filter = (("cree_le", admin.DateFieldListFilter),)
    autocomplete_fields = ("inscription", "acteur")
    readonly_fields = ("cree_le", "modifie_le")

AUTO_FIELDS_OPTION = ("intitule", "description")

@admin.register(OptionCircuit)
class OptionCircuitAdmin(TabbedTranslationAdmin):
    list_display = ("circuit", "code", "intitule", "categorie",
                    "prix_unitaire", "facture_par_personne",
                    "quantite_min", "quantite_max")
    list_filter = ("categorie", "facture_par_personne", "circuit")
    search_fields = ("code", "intitule", "circuit__code", "circuit__nom")
    autocomplete_fields = ("circuit",)

    def save_model(self, request, obj, form, change):
        if auto_translate_instance(obj, AUTO_FIELDS_OPTION):
            pass
        super().save_model(request, obj, form, change)

    @admin.action(description="Auto-traduire FR → EN (intitulé/description)")
    def action_autotranslate(self, request, queryset):
        n = 0
        for o in queryset:
            if auto_translate_instance(o, AUTO_FIELDS_OPTION):
                o.save()
                n += 1
        self.message_user(request, f"{n} option(s) mises à jour.")

    actions = [action_autotranslate]

@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "is_active", "created_at", "source")
    search_fields = ("email",)
    list_filter = ("is_active", "source")


@admin.register(PasswordHistory)
class PasswordHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "user__email")


from .models import ContactMessage

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("cree_le", "nom", "prenom", "email", "type_demande", "interesse_circuit", "statut_circuit", "circuit", "traite")
    list_filter = ("type_demande", "interesse_circuit", "statut_circuit", "traite", ("cree_le", admin.DateFieldListFilter))
    search_fields = ("nom", "prenom", "email", "telephone", "message", "adresse")
    autocomplete_fields = ("circuit",)
    readonly_fields = ("ip", "user_agent", "cree_le", "modifie_le")
    fieldsets = (
        ("Coordonnées", {"fields": (("prenom", "nom"), ("email", "telephone"), "adresse")}),
        ("Intérêt circuit", {"fields": ("interesse_circuit", "statut_circuit", "circuit")}),
        ("Demande", {"fields": ("type_demande", "message", "consent")}),
        ("Suivi", {"fields": ("traite", "ip", "user_agent", ("cree_le", "modifie_le"))}),
    )

# -*- coding: utf-8 -*-
from django.contrib import admin
from django.utils.html import format_html

from .models import BaladeJour, DemandeProgrammeBalade


@admin.register(BaladeJour)
class BaladeJourAdmin(admin.ModelAdmin):
    list_display = (
        "date_debut",
        "date_fin",
        "date_affichage_admin",
        "titre",
        "guide",
        "actif",
        "ordre",
    )
    list_filter = ("actif", "guide", "date_debut")
    search_fields = ("titre", "guide", "date_affichage")
    ordering = ("date_debut", "ordre", "titre")
    list_editable = ("actif", "ordre", "guide")
    date_hierarchy = "date_debut"

    fieldsets = (
        ("Dates", {
            "fields": ("date_debut", "date_fin", "date_affichage")
        }),
        ("Informations balade", {
            "fields": ("titre", "guide")
        }),
        ("Affichage", {
            "fields": ("actif", "ordre")
        }),
    )

    @admin.display(description="Date affichée")
    def date_affichage_admin(self, obj):
        return obj.date_humaine()


@admin.action(description="Marquer les demandes sélectionnées comme traitées")
def marquer_comme_traite(modeladmin, request, queryset):
    queryset.update(traite=True)


@admin.action(description="Marquer les demandes sélectionnées comme non traitées")
def marquer_comme_non_traite(modeladmin, request, queryset):
    queryset.update(traite=False)


@admin.register(DemandeProgrammeBalade)
class DemandeProgrammeBaladeAdmin(admin.ModelAdmin):
    list_display = (
        "cree_le",
        "nom_complet_admin",
        "email",
        "telephone",
        "nb_balades",
        "traite_badge",
    )
    list_filter = ("traite", "cree_le", "balades")
    search_fields = ("prenom", "nom", "email", "telephone", "commentaire")
    ordering = ("-cree_le",)
    filter_horizontal = ("balades",)
    readonly_fields = ("cree_le", "modifie_le", "ip", "user_agent", "balades_resume")
    actions = (marquer_comme_traite, marquer_comme_non_traite)

    fieldsets = (
        ("Client", {
            "fields": ("prenom", "nom", "email", "telephone")
        }),
        ("Sélection", {
            "fields": ("balades", "balades_resume", "commentaire")
        }),
        ("Suivi", {
            "fields": ("traite", "source")
        }),
        ("Technique", {
            "classes": ("collapse",),
            "fields": ("ip", "user_agent", "cree_le", "modifie_le")
        }),
    )

    @admin.display(description="Client")
    def nom_complet_admin(self, obj):
        return obj.nom_complet

    @admin.display(description="Balades")
    def nb_balades(self, obj):
        return obj.balades.count()

    @admin.display(description="Statut")
    def traite_badge(self, obj):
        if obj.traite:
            return format_html(
                '<span style="display:inline-block;padding:4px 10px;border-radius:999px;'
                'background:#dcfce7;color:#166534;font-weight:700;">Traité</span>'
            )
        return format_html(
            '<span style="display:inline-block;padding:4px 10px;border-radius:999px;'
            'background:#fee2e2;color:#991b1b;font-weight:700;">À traiter</span>'
        )

    @admin.display(description="Balades sélectionnées")
    def balades_resume(self, obj):
        items = obj.balades.all().order_by("date_debut", "ordre", "titre")
        if not items.exists():
            return "Aucune balade"

        html = ["<ul style='margin:0;padding-left:18px;'>"]
        for b in items:
            html.append(
                f"<li><strong>{b.date_humaine()}</strong> — {b.titre} "
                f"<em>(Guide : {b.guide or 'libre'})</em></li>"
            )
        html.append("</ul>")
        return format_html("".join(html))


class Programme2027SelectionInline(admin.TabularInline):
    model = Programme2027Selection
    extra = 0
    fields = ("circuit", "niveau_interet", "participants", "mode_prefere", "commentaire")
    autocomplete_fields = ("circuit",)


@admin.register(Programme2027Circuit)
class Programme2027CircuitAdmin(admin.ModelAdmin):
    list_display = ("ordre", "titre", "mois", "duree", "formule", "categorie", "actif")
    list_filter = ("actif", "categorie", "mois")
    search_fields = ("titre", "mois", "duree", "formule", "slug")
    list_editable = ("ordre", "actif")
    prepopulated_fields = {"slug": ("titre", "mois")}
    ordering = ("ordre", "titre")


@admin.register(Programme2027Interest)
class Programme2027InterestAdmin(admin.ModelAdmin):
    list_display = ("cree_le", "nom_complet", "email", "telephone", "nb_circuits", "delai_decision", "traite")
    list_filter = ("traite", "delai_decision", "newsletter_optin", "cree_le")
    search_fields = ("prenom", "nom", "email", "telephone", "localite", "pays", "vehicule", "commentaire")
    readonly_fields = ("cree_le", "modifie_le", "ip", "user_agent")
    inlines = (Programme2027SelectionInline,)
    actions = (marquer_comme_traite, marquer_comme_non_traite)

    @admin.display(description="Circuits")
    def nb_circuits(self, obj):
        return obj.selections.count()
