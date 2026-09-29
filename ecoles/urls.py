from django.urls import path
from . import views

app_name = 'ecoles'

urlpatterns = [
    # =====================================================
    # Années scolaires
    # =====================================================
    path('annees/', views.annee_liste, name='annee_liste'),
    path('annees/creer/', views.annee_creer, name='annee_creer'),
    path('annees/<int:annee_id>/activer/', views.annee_activer, name='annee_activer'),
    path('annees/<int:annee_id>/rouvrir/', views.annee_rouvrir, name='annee_rouvrir'),

    # =====================================================
    # Trimestres
    # =====================================================
    path('trimestres/', views.trimestre_liste, name='trimestre_liste'),
    path('trimestres/generer/', views.trimestre_generer, name='trimestre_generer'),
    path('trimestres/<int:trimestre_id>/cloturer/', views.trimestre_cloturer, name='trimestre_cloturer'),

    # =====================================================
    # Configuration
    # =====================================================
    path('configuration/', views.configuration_etablissement, name='configuration'),

    # =====================================================
    # Classes
    # =====================================================
    path('classes/', views.classe_liste, name='classe_liste'),
    path('classes/creer/', views.classe_creer, name='classe_creer'),
    path('classes/<int:classe_id>/modifier/', views.classe_modifier, name='classe_modifier'),
    path('classes/<int:classe_id>/supprimer/', views.classe_supprimer, name='classe_supprimer'),
    path('classes/<int:classe_id>/titulaire/', views.classe_titulaire, name='classe_titulaire'),

    # =====================================================
    # Matières
    # =====================================================
    path('matieres/', views.matiere_liste, name='matiere_liste'),
    path('matieres/creer/', views.matiere_creer, name='matiere_creer'),
    path('matieres/<int:matiere_id>/modifier/', views.matiere_modifier, name='matiere_modifier'),
    path('matieres/<int:matiere_id>/supprimer/', views.matiere_supprimer, name='matiere_supprimer'),

    # =====================================================
    # Matières par classe
    # =====================================================
    path('matieres-classes/', views.matiereclasse_choisir, name='matiereclasse_choisir'),
    path('matieres-classes/<int:classe_id>/', views.matiereclasse_liste, name='matiereclasse_liste'),
    path('matieres-classes/<int:classe_id>/affecter/', views.matiereclasse_affecter, name='matiereclasse_affecter'),
    path('matieres-classes/<int:classe_id>/affecter-masse/', views.matiereclasse_affecter_masse, name='matiereclasse_affecter_masse'),
    path('matieres-classes/affectation/<int:affectation_id>/modifier/', views.matiereclasse_modifier, name='matiereclasse_modifier'),
    path('matieres-classes/affectation/<int:affectation_id>/supprimer/', views.matiereclasse_supprimer, name='matiereclasse_supprimer'),

    # =====================================================
    # Élèves
    # =====================================================
    path('eleves/', views.eleve_liste, name='eleve_liste'),
    path('eleves/creer/', views.eleve_creer, name='eleve_creer'),
    path('eleves/<int:eleve_id>/', views.eleve_detail, name='eleve_detail'),
    path('eleves/<int:eleve_id>/modifier/', views.eleve_modifier, name='eleve_modifier'),
    path('eleves/<int:eleve_id>/supprimer/', views.eleve_supprimer, name='eleve_supprimer'),
    path('eleves/<int:eleve_id>/inscrire/', views.eleve_inscrire, name='eleve_inscrire'),

    # =====================================================
    # Export / Import élèves
    # =====================================================
    path('eleves/export/excel/', views.eleve_export_excel, name='eleve_export_excel'),
    path('eleves/export/csv/', views.eleve_export_csv, name='eleve_export_csv'),
    path('eleves/export/pdf/', views.eleve_export_pdf, name='eleve_export_pdf'),
    path('eleves/modele-excel/', views.eleve_modele_excel, name='eleve_modele_excel'),
    path('eleves/importer/', views.eleve_importer, name='eleve_importer'),

    # =====================================================
    # Notes
    # =====================================================
    path('notes/', views.notes_selection, name='notes_selection'),
    path('notes/saisie/', views.notes_saisie, name='notes_saisie'),
    path('notes/verification/', views.notes_verification, name='notes_verification'),
    path('api/matieres/<int:classe_id>/', views.api_matieres_par_classe, name='api_matieres_par_classe'),
]


# =====================================================
# BULLETINS (Session 9)
# =====================================================
from django.urls import path as _path_bul
from . import views_bulletins as _views_bul

urlpatterns += [
    _path_bul('bulletins/', _views_bul.bulletin_selection, name='bulletin_selection'),
    _path_bul('bulletins/eleve/<int:eleve_id>/trimestre/<int:trimestre_id>/pdf/',
              _views_bul.bulletin_pdf_eleve, name='bulletin_pdf_eleve'),
    _path_bul('bulletins/classe/<int:classe_id>/trimestre/<int:trimestre_id>/pdf/',
              _views_bul.bulletin_pdf_classe, name='bulletin_pdf_classe'),
]


# =====================================================
# CARTES SCOLAIRES (Session 10)
# =====================================================
from django.urls import path as _path_cartes
from . import views_cartes as _views_cartes

urlpatterns += [
    _path_cartes('cartes/', _views_cartes.carte_selection, name='carte_selection'),
    _path_cartes('cartes/classe/<int:classe_id>/pdf/',
                 _views_cartes.carte_pdf_classe, name='carte_pdf_classe'),
    _path_cartes('cartes/eleve/<int:eleve_id>/pdf/',
                 _views_cartes.carte_pdf_eleve, name='carte_pdf_eleve'),
]


# =====================================================
# FICHE ÉLÈVE PDF (Session 1)
# =====================================================
from django.urls import path as _path_fiche
from . import views_fiche as _views_fiche

urlpatterns += [
    _path_fiche('eleves/<int:eleve_id>/fiche-pdf/',
                _views_fiche.eleve_fiche_pdf, name='eleve_fiche_pdf'),
]


# =====================================================
# RELEVÉS DE NOTES CLASSE (Session 2)
# =====================================================
from django.urls import path as _path_releve
from . import views_releves as _views_releves

urlpatterns += [
    _path_releve('releves/', _views_releves.releve_selection, name='releve_selection'),
    _path_releve('releves/classe/<int:classe_id>/trimestre/<int:trimestre_id>/pdf/',
                 _views_releves.releve_pdf_classe, name='releve_pdf_classe'),
]


# =====================================================
# STATISTIQUES SCOLAIRES (Session 2bis)
# =====================================================
from django.urls import path as _path_stats
from . import views_stats as _views_stats

urlpatterns += [
    _path_stats('stats/', _views_stats.stats_selection, name='stats_selection'),
    _path_stats('stats/composition/classe/<int:classe_id>/trimestre/<int:trimestre_id>/pdf/',
                _views_stats.stats_composition_pdf, name='stats_composition_pdf'),
]


# =====================================================
# STATISTIQUES TRIMESTRE COMPLET (Page 2)
# =====================================================
from django.urls import path as _path_strim
from . import views_stats as _views_strim

urlpatterns += [
    _path_strim('stats/trimestre/classe/<int:classe_id>/trimestre/<int:trimestre_id>/pdf/',
                _views_strim.stats_trimestre_pdf, name='stats_trimestre_pdf'),
]


# =====================================================
# STATISTIQUES ANNUELLES (Page 3)
# =====================================================
from django.urls import path as _path_sann
from . import views_stats as _views_sann

urlpatterns += [
    _path_sann('stats/annuelles/classe/<int:classe_id>/pdf/',
               _views_sann.stats_annuelles_pdf, name='stats_annuelles_pdf'),
]


# =====================================================
# STATISTIQUES ÉTABLISSEMENT (Page 4)
# =====================================================
from django.urls import path as _path_setab
from . import views_stats as _views_setab

urlpatterns += [
    _path_setab('stats/etablissement/pdf/',
                _views_setab.stats_etablissement_pdf, name='stats_etablissement_pdf'),
]


# =====================================================
# ATTESTATIONS (Session 3)
# =====================================================
from django.urls import path as _path_attest
from . import views_attestations as _views_attest

urlpatterns += [
    _path_attest('attestations/', _views_attest.attestation_selection, name='attestation_selection'),
    _path_attest('attestations/eleve/<int:eleve_id>/<str:type_attestation>/pdf/',
                 _views_attest.attestation_pdf, name='attestation_pdf'),
]


# =====================================================
# FICHE VIERGE (à imprimer)
# =====================================================
from django.urls import path as _path_fv
from . import views_fiche as _views_fv

urlpatterns += [
    _path_fv('eleves/fiche-vierge-pdf/', _views_fv.eleve_fiche_vierge_pdf, name='eleve_fiche_vierge_pdf'),
]


# =====================================================
# FICHE PRÉ-REMPLIE
# =====================================================
urlpatterns += [
    _path_fv('eleves/<int:eleve_id>/fiche-preremplie-pdf/',
             _views_fv.eleve_fiche_preremplie_pdf, name='eleve_fiche_preremplie_pdf'),
]


# =====================================================
# VÉRIFICATION DE LA CONFIGURATION (Session 16)
# =====================================================
from django.urls import path as _path_verif

urlpatterns += [
    _path_verif('verification-config/',
                views.verification_config,
                name='verification_config'),
]


# =====================================================
# LISTES DE CLASSE (Session 17)
# =====================================================
from django.urls import path as _path_listes
from . import views_listes as _views_listes

urlpatterns += [
    _path_listes('listes/', _views_listes.liste_selection, name='liste_selection'),
    _path_listes('listes/classe/<int:classe_id>/pdf/',
                 _views_listes.liste_pdf_classe, name='liste_pdf_classe'),
]


# =====================================================
# LISTE DE PRÉSENCE (Session 17b)
# =====================================================
urlpatterns += [
    _path_listes('listes/presence/classe/<int:classe_id>/pdf/',
                 _views_listes.presence_pdf_classe, name='presence_pdf_classe'),
]


# =====================================================
# DISCIPLINE (Session 18)
# =====================================================
from django.urls import path as _path_disc
from . import views_discipline as _views_disc

urlpatterns += [
    _path_disc('discipline/', _views_disc.discipline_menu, name='discipline_menu'),
    _path_disc('discipline/incidents/', _views_disc.incident_liste, name='incident_liste'),
    _path_disc('discipline/incidents/creer/', _views_disc.incident_creer, name='incident_creer'),
    _path_disc('discipline/incidents/<int:incident_id>/', _views_disc.incident_detail, name='incident_detail'),
    _path_disc('discipline/incidents/<int:incident_id>/modifier/', _views_disc.incident_modifier, name='incident_modifier'),
    _path_disc('discipline/incidents/<int:incident_id>/supprimer/', _views_disc.incident_supprimer, name='incident_supprimer'),
    _path_disc('discipline/incidents/<int:incident_id>/sanction/', _views_disc.sanction_creer, name='sanction_creer'),
    _path_disc('discipline/sanctions/<int:sanction_id>/supprimer/', _views_disc.sanction_supprimer, name='sanction_supprimer'),
    _path_disc('discipline/recherche-eleve/', _views_disc.eleve_recherche, name='eleve_recherche'),
    _path_disc('discipline/eleve/<int:eleve_id>/historique/', _views_disc.eleve_historique, name='eleve_historique'),
]


# =====================================================
# API JSON Discipline — élèves par classe (Session 18)
# =====================================================
urlpatterns += [
    _path_disc('api/eleves-par-classe/<int:classe_id>/',
               _views_disc.api_eleves_par_classe,
               name='api_eleves_par_classe'),
]


# =====================================================
# PRÉSENCES (Session 20)
# =====================================================
from django.urls import path as _path_pres
from . import views_presences as _views_pres

urlpatterns += [
    _path_pres('presences/', _views_pres.presence_selection, name='presence_selection'),
    _path_pres('presences/saisie/', _views_pres.presence_saisie, name='presence_saisie'),
    _path_pres('presences/historique/classe/<int:classe_id>/',
               _views_pres.presence_historique_classe, name='presence_historique_classe'),
    _path_pres('presences/historique/eleve/<int:eleve_id>/',
               _views_pres.presence_historique_eleve, name='presence_historique_eleve'),
    _path_pres('presences/recherche-eleve/',
               _views_pres.presence_recherche_eleve, name='presence_recherche_eleve'),
    _path_pres('presences/api/stats/<int:classe_id>/',
               _views_pres.api_stats_presence_jour, name='api_stats_presence_jour'),
]


# =====================================================
# RÉINSCRIPTION (Session 21)
# =====================================================
from django.urls import path as _path_reins
from . import views_reinscription as _views_reins

urlpatterns += [
    _path_reins('reinscription/', _views_reins.reinscription_preview, name='reinscription_preview'),
    _path_reins('reinscription/executer/', _views_reins.reinscription_executer, name='reinscription_executer'),
]
