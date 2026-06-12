# circuitMoto/urls.py

from django.urls import path # type: ignore
from django.contrib.auth import views as auth_views # type:ignore
from django.urls import reverse_lazy

from .views import InscriptionWizardView, InscriptionWizardEditView, newsletter_subscribe, circuit_detail, inscription_lookup, CircuitPublicList
from circuitMoto import admin_views

from .views import (
    contact,
    api_circuits_by_statut,
    balades_1_jour,
    balades_1_jour_success,
    balades_email_landing,
    balades_1_jour_lien,
    programme,
    programme_2027,
    programme_2027_success,
)

create_wizard = InscriptionWizardView.as_view(
    url_name='inscription_create_step',
    done_step_name='done',
)

edit_wizard = InscriptionWizardEditView.as_view(
    url_name='inscription_edit_step',
    done_step_name='done',
)

urlpatterns = [

    # --- Page "Déjà inscrit ?" ---
    path("inscription/retrouver/", inscription_lookup, name="inscription_lookup"),


    # Création
    path('inscription/', create_wizard,                                      name='inscription_create_start'), # démarre au 1er step
    path('inscription/<str:step>/', create_wizard,                           name='inscription_create_step'),  # étapes nommées

    # Édition
    path('inscription/<uuid:id_public>/modifier/', edit_wizard,              name='inscription_edit_start'),
    path('inscription/<uuid:id_public>/modifier/<str:step>/', edit_wizard,   name='inscription_edit_step'),

    # path('circuit/<int:pk>/', circuit_detail, name='circuit_detail'),
    path("circuit/<slug:code>/", circuit_detail, name="circuit_detail"),

    path("circuits/", CircuitPublicList.as_view(), name="circuits_public"),

    # Auth (templates fournis optionnellement plus bas)
    path(
        'accounts/login/',
        auth_views.LoginView.as_view(
            template_name='circuitMoto/auth/login.html',
            success_url=reverse_lazy('home'),          # 👈 redirection après login
            redirect_authenticated_user=True           # si déjà connecté, renvoie vers success_url
        ),
        name='login'
    ),

    path(
        'accounts/password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='circuitMoto/auth/password_reset.html',
            email_template_name='circuitMoto/auth/password_reset_email.html',
            html_email_template_name='circuitMoto/auth/password_reset_email_html.html',
            subject_template_name='circuitMoto/auth/password_reset_subject.txt',
            success_url=reverse_lazy('password_reset_done'),
        ),
        name='password_reset'
    ),
    path(
        'accounts/password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='circuitMoto/auth/password_reset_done.html'
        ),
        name='password_reset_done'
    ),
    path(
        'accounts/reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='circuitMoto/auth/password_reset_confirm.html',
            success_url=reverse_lazy('password_reset_complete')
        ),
        name='password_reset_confirm'
    ),
    path(
        'accounts/reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='circuitMoto/auth/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),


    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='home'),  name='logout'),    

    # Back-office (staff only)
    path('backoffice/',                           admin_views.dashboard,       name='bo_dashboard'),
    path('backoffice/circuits/',                  admin_views.circuit_list,    name='bo_circuit_list'),
    path('backoffice/circuits/nouveau/',          admin_views.circuit_create,  name='bo_circuit_create'),
    path("backoffice/circuits/<int:pk>/",         admin_views.circuit_detail,  name="bo_circuit_detail"),
    path('backoffice/circuits/<int:pk>/edit/',    admin_views.circuit_edit,    name='bo_circuit_edit'),
    path('backoffice/inscriptions/',              admin_views.inscription_list,name='bo_inscription_list'),
    path('backoffice/paiements/excel/',           admin_views.payment_excel_import, name='bo_payment_excel_import'),
    path('backoffice/paiements/excel/modele/',    admin_views.payment_excel_template_xlsx, name='bo_payment_excel_template'),
    path('backoffice/personnes/',                 admin_views.personne_list,   name='bo_personne_list'),
    path("bo/personnes/<int:pk>/",                admin_views.personne_detail, name="bo_personne_detail"),
    path('backoffice/emailing/',                  admin_views.emailing,        name='bo_emailing'),
    path("bo/newsletter/",                        admin_views.newsletter_broadcast, name="bo_newsletter_broadcast"),
    path("backoffice/inscriptions/<int:pk>/supprimer/",
        admin_views.inscription_delete,
        name="bo_inscription_delete"),
    path('backoffice/personnes/nouveau/', admin_views.personne_create,             name='bo_personne_create'),
    path('backoffice/personnes/<int:pk>/inscrire/', admin_views.inscrire_personne, name='bo_inscrire_personne'),
    path('backoffice/stats/', admin_views.stats, name='bo_stats'),
    path('backoffice/utilisateurs/nouveau/', admin_views.user_create, name='bo_user_create'),
    path('account/change-password-first/', admin_views.password_change_first, name='force_password_change'),
    path('account/password-change/', admin_views.password_change_self, name='account_password_change'),
    path('backoffice/settings/email-flags/', admin_views.email_flags_set, name='bo_email_flags_set'),

    path("backoffice/personnes/export/", admin_views.personnes_export_xlsx, name="bo_personnes_export"),
    path("backoffice/inscriptions/export-reservations/", admin_views.reservations_export_xlsx, name="bo_reservations_export"),

    path("api/newsletter/subscribe/",           newsletter_subscribe, name="newsletter_subscribe"),

    path("contact/", contact, name="contact"),

    path("balades-1-jour/", balades_1_jour, name="balades_1_jour"),
    path("balades-1-jour/succes/", balades_1_jour_success, name="balades_1_jour_success"),
    path("balades-1-jour/selection/", balades_email_landing, name="balades_email_landing"),
    path("balades-1-jour/lien/<slug:slug>/", balades_1_jour_lien, name="balades_1_jour_lien"),

    # BALADES 1 JOUR — BACK OFFICE
    path("backoffice/balades-1-jour/", admin_views.balade_list, name="bo_balade_list"),
    path("backoffice/balades-1-jour/nouveau/", admin_views.balade_create, name="bo_balade_create"),
    path("backoffice/balades-1-jour/<int:pk>/modifier/", admin_views.balade_edit, name="bo_balade_edit"),
    path("backoffice/demandes-balades/", admin_views.demande_balade_list, name="bo_demande_balade_list"),
    path("backoffice/balades/demandes-par-balade/", admin_views.demande_balade_par_balade, name="bo_demande_balade_par_balade"),
    path("backoffice/balades/demandes/<int:pk>/", admin_views.demande_balade_detail, name="bo_demande_balade_detail"),

    # PRE PROGRAMME 2027
    path("programme-2027/", programme_2027, name="programme_2027"),
    path("programme-2027/succes/", programme_2027_success, name="programme_2027_success"),
    path("backoffice/programme-2027/interesses/", admin_views.programme_2027_interest_list, name="bo_programme_2027_interests"),
    path("backoffice/programme-2027/circuits/", admin_views.programme_2027_by_circuit, name="bo_programme_2027_by_circuit"),
    path("backoffice/programme-2027/circuits/<int:pk>/interesses/", admin_views.programme_2027_circuit_detail, name="bo_programme_2027_circuit_detail"),

    path("api/circuits/by-statut/", api_circuits_by_statut, name="api_circuits_by_statut"),
    
    path("bo/backup/download/", admin_views.bo_backup_download, name="bo_backup_download"),

    path("programme/", programme, name="programme")

]
