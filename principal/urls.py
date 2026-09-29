from django.urls import path
from . import views

app_name = 'principal'

urlpatterns = [
    # Établissements
    path('etablissements/', views.etablissement_liste, name='etablissement_liste'),
    path('etablissements/creer/', views.etablissement_creer, name='etablissement_creer'),
    path('etablissements/creer/succes/', views.etablissement_creer_succes, name='etablissement_creer_succes'),
    path('etablissements/<int:etab_id>/', views.etablissement_detail, name='etablissement_detail'),
    path('etablissements/<int:etab_id>/modifier/', views.etablissement_modifier, name='etablissement_modifier'),
    path('etablissements/<int:etab_id>/suspendre/', views.etablissement_suspendre, name='etablissement_suspendre'),
    path('etablissements/<int:etab_id>/activer/', views.etablissement_activer, name='etablissement_activer'),
    path('etablissements/<int:etab_id>/supprimer/', views.etablissement_supprimer, name='etablissement_supprimer'),

    # Utilisateurs d'un établissement
    path('etablissements/<int:etab_id>/utilisateurs/ajouter/', views.utilisateur_ajouter, name='utilisateur_ajouter'),
    path('etablissements/<int:etab_id>/utilisateurs/ajouter/succes/', views.utilisateur_ajouter_succes, name='utilisateur_ajouter_succes'),
    path('utilisateurs/<int:profil_id>/modifier/', views.utilisateur_modifier, name='utilisateur_modifier'),
    path('utilisateurs/<int:profil_id>/desactiver/', views.utilisateur_desactiver, name='utilisateur_desactiver'),
    path('utilisateurs/<int:profil_id>/activer/', views.utilisateur_activer, name='utilisateur_activer'),
    path('utilisateurs/<int:profil_id>/supprimer/', views.utilisateur_supprimer, name='utilisateur_supprimer'),
    path('utilisateurs/<int:profil_id>/reset-password/', views.utilisateur_reset_password, name='utilisateur_reset_password'),
    path('utilisateurs/<int:profil_id>/reset-password/succes/', views.utilisateur_reset_succes, name='utilisateur_reset_succes'),

    # Liste globale
    path('utilisateurs/', views.utilisateur_liste_globale, name='utilisateur_liste'),
]
