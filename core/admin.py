"""
ScolaEdu_AKEK — Configuration Admin Django.
Filtrage automatique par établissement selon le rôle de l'utilisateur.
"""

from django.contrib import admin
from .models import (
    Etablissement, ProfilUtilisateur, Matiere, Classe,
    Enseignant, MatiereClasse, Eleve, Inscription, Trimestre, Note,
    AnneeScolaire, ConfigurationEtablissement
)


# =====================================================
# HELPERS DE FILTRAGE
# =====================================================
def _get_etab_user(request):
    try:
        return request.user.profil.etablissement
    except Exception:
        return None


def _get_role_user(request):
    try:
        return request.user.profil.role
    except Exception:
        return None


def _est_admin_principal(request):
    return _get_role_user(request) == 'admin_principal'


def _filtrer_par_etablissement(qs, request, champ='etablissement'):
    if _est_admin_principal(request):
        return qs
    etab = _get_etab_user(request)
    if not etab:
        return qs.none()
    return qs.filter(**{champ: etab})


# =====================================================
# ÉTABLISSEMENT
# =====================================================
@admin.register(Etablissement)
class EtablissementAdmin(admin.ModelAdmin):
    list_display = ('nom', 'code', 'type_etablissement', 'ville', 'telephone', 'bp', 'actif')
    list_filter = ('type_etablissement', 'actif', 'ville')
    search_fields = ('nom', 'code', 'numero_agrement')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if _est_admin_principal(request):
            return qs
        etab = _get_etab_user(request)
        if not etab:
            return qs.none()
        return qs.filter(id=etab.id)


# =====================================================
# PROFIL UTILISATEUR
# =====================================================
@admin.register(ProfilUtilisateur)
class ProfilUtilisateurAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'etablissement', 'telephone')
    list_filter = ('role', 'etablissement')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return _filtrer_par_etablissement(qs, request)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "etablissement":
            kwargs["queryset"] = _filtrer_par_etablissement(
                Etablissement.objects.all(), request, 'id'
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# =====================================================
# ANNÉE SCOLAIRE
# =====================================================
@admin.register(AnneeScolaire)
class AnneeScolaireAdmin(admin.ModelAdmin):
    list_display = ('libelle', 'etablissement', 'date_debut', 'date_fin', 'en_cours', 'cloturee')
    list_filter = ('etablissement', 'en_cours', 'cloturee')
    search_fields = ('libelle',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return _filtrer_par_etablissement(qs, request)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "etablissement":
            kwargs["queryset"] = _filtrer_par_etablissement(
                Etablissement.objects.all(), request, 'id'
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# =====================================================
# MATIÈRE
# =====================================================
@admin.register(Matiere)
class MatiereAdmin(admin.ModelAdmin):
    list_display = ('nom', 'code', 'coefficient', 'ordre', 'etablissement', 'annee_scolaire')
    list_filter = ('etablissement', 'annee_scolaire')
    search_fields = ('nom', 'code')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return _filtrer_par_etablissement(qs, request)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "etablissement":
            kwargs["queryset"] = _filtrer_par_etablissement(
                Etablissement.objects.all(), request, 'id'
            )
        if db_field.name == "annee_scolaire":
            kwargs["queryset"] = _filtrer_par_etablissement(
                AnneeScolaire.objects.all(), request
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# =====================================================
# CLASSE
# =====================================================
@admin.register(Classe)
class ClasseAdmin(admin.ModelAdmin):
    list_display = ('nom', 'niveau', 'etablissement', 'annee_scolaire', 'titulaire', 'effectif_max')
    list_filter = ('etablissement', 'annee_scolaire', 'niveau')
    search_fields = ('nom',)
    autocomplete_fields = ('titulaire',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return _filtrer_par_etablissement(qs, request)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "etablissement":
            kwargs["queryset"] = _filtrer_par_etablissement(
                Etablissement.objects.all(), request, 'id'
            )
        if db_field.name == "annee_scolaire":
            kwargs["queryset"] = _filtrer_par_etablissement(
                AnneeScolaire.objects.all(), request
            )
        if db_field.name == "titulaire":
            kwargs["queryset"] = _filtrer_par_etablissement(
                Enseignant.objects.all(), request
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# =====================================================
# ENSEIGNANT
# =====================================================
@admin.register(Enseignant)
class EnseignantAdmin(admin.ModelAdmin):
    list_display = ('user', 'etablissement', 'matricule', 'specialite', 'telephone')
    list_filter = ('etablissement', 'specialite')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'matricule')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return _filtrer_par_etablissement(qs, request)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "etablissement":
            kwargs["queryset"] = _filtrer_par_etablissement(
                Etablissement.objects.all(), request, 'id'
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# =====================================================
# MATIÈRE PAR CLASSE (le plus important !)
# =====================================================
@admin.register(MatiereClasse)
class MatiereClasseAdmin(admin.ModelAdmin):
    list_display = ('classe', 'matiere', 'coefficient', 'enseignant')
    list_filter = ('classe__etablissement', 'classe__annee_scolaire', 'enseignant')
    search_fields = ('classe__nom', 'matiere__nom', 'enseignant__user__username')
    autocomplete_fields = ('classe', 'matiere', 'enseignant')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return _filtrer_par_etablissement(qs, request, 'classe__etablissement')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "classe":
            kwargs["queryset"] = _filtrer_par_etablissement(
                Classe.objects.all(), request
            )
        if db_field.name == "matiere":
            kwargs["queryset"] = _filtrer_par_etablissement(
                Matiere.objects.all(), request
            )
        if db_field.name == "enseignant":
            kwargs["queryset"] = _filtrer_par_etablissement(
                Enseignant.objects.all(), request
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# =====================================================
# ÉLÈVE
# =====================================================
@admin.register(Eleve)
class EleveAdmin(admin.ModelAdmin):
    list_display = ('matricule', 'nom', 'prenom', 'sexe', 'etablissement', 'actif')
    list_filter = ('etablissement', 'sexe', 'actif')
    search_fields = ('matricule', 'nom', 'prenom')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return _filtrer_par_etablissement(qs, request)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "etablissement":
            kwargs["queryset"] = _filtrer_par_etablissement(
                Etablissement.objects.all(), request, 'id'
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# =====================================================
# INSCRIPTION
# =====================================================
@admin.register(Inscription)
class InscriptionAdmin(admin.ModelAdmin):
    list_display = ('eleve', 'classe', 'annee_scolaire', 'date_inscription', 'actif')
    list_filter = ('classe__etablissement', 'annee_scolaire', 'actif')
    search_fields = ('eleve__nom', 'eleve__prenom', 'eleve__matricule')
    autocomplete_fields = ('eleve', 'classe')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return _filtrer_par_etablissement(qs, request, 'classe__etablissement')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "classe":
            kwargs["queryset"] = _filtrer_par_etablissement(
                Classe.objects.all(), request
            )
        if db_field.name == "eleve":
            kwargs["queryset"] = _filtrer_par_etablissement(
                Eleve.objects.all(), request
            )
        if db_field.name == "annee_scolaire":
            kwargs["queryset"] = _filtrer_par_etablissement(
                AnneeScolaire.objects.all(), request
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# =====================================================
# TRIMESTRE
# =====================================================
@admin.register(Trimestre)
class TrimestreAdmin(admin.ModelAdmin):
    list_display = ('get_numero_display', 'annee_scolaire', 'etablissement', 'date_debut', 'date_fin', 'cloture')
    list_filter = ('etablissement', 'annee_scolaire', 'cloture')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return _filtrer_par_etablissement(qs, request)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "etablissement":
            kwargs["queryset"] = _filtrer_par_etablissement(
                Etablissement.objects.all(), request, 'id'
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# =====================================================
# NOTE
# =====================================================
@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = (
        'eleve', 'matiere', 'trimestre',
        'note_devoir1', 'note_devoir2', 'note_composition',
        'moyenne_devoirs', 'moyenne_finale'
    )
    list_filter = ('trimestre__etablissement', 'matiere', 'enseignant')
    search_fields = ('eleve__nom', 'eleve__prenom', 'eleve__matricule')
    autocomplete_fields = ('eleve', 'matiere', 'enseignant')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return _filtrer_par_etablissement(qs, request, 'eleve__etablissement')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "eleve":
            kwargs["queryset"] = _filtrer_par_etablissement(
                Eleve.objects.all(), request
            )
        if db_field.name == "matiere":
            kwargs["queryset"] = _filtrer_par_etablissement(
                Matiere.objects.all(), request
            )
        if db_field.name == "enseignant":
            kwargs["queryset"] = _filtrer_par_etablissement(
                Enseignant.objects.all(), request
            )
        if db_field.name == "trimestre":
            kwargs["queryset"] = _filtrer_par_etablissement(
                Trimestre.objects.all(), request
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# =====================================================
# CONFIGURATION ÉTABLISSEMENT
# =====================================================
@admin.register(ConfigurationEtablissement)
class ConfigurationEtablissementAdmin(admin.ModelAdmin):
    list_display = (
        'etablissement', 'nom_officiel', 'nom_chef',
        'titre_chef', 'note_passage', 'date_mise_a_jour'
    )
    search_fields = ('etablissement__nom', 'nom_chef', 'nom_officiel')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return _filtrer_par_etablissement(qs, request)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "etablissement":
            kwargs["queryset"] = _filtrer_par_etablissement(
                Etablissement.objects.all(), request, 'id'
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
