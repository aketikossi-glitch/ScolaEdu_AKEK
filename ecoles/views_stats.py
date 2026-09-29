"""
ScolaEdu_AKEK — Vues pour les statistiques scolaires PDF (Session 2bis).
"""
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse

from core.models import (
    AnneeScolaire, Trimestre, Classe, Inscription,
    ConfigurationEtablissement,
)
from core.stats_scolaires_pdf import exporter_stats_composition_pdf

from .views import (
    _get_etablissement_user,
    _get_enseignant_user,
    _get_classes_autorisees,
    _verifier_acces_classe,
)


# =====================================================
# PAGE DE SÉLECTION
# =====================================================
@login_required
def stats_selection(request):
    """Page de sélection : classe + trimestre + type de stats."""
    etab = _get_etablissement_user(request)
    if not etab:
        messages.error(request, "Aucun établissement lié à votre compte.")
        return redirect('accounts:logout')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.warning(request, "Aucune année scolaire active.")
        return redirect('ecoles:annee_creer')

    classes_autorisees = _get_classes_autorisees(request)
    trimestres = Trimestre.objects.filter(
        etablissement=etab,
        annee_scolaire=annee.libelle,
    ).order_by('numero')

    est_enseignant = _get_enseignant_user(request) is not None

    if not classes_autorisees.exists():
        return render(request, 'ecoles/stats_selection.html', {
            'etablissement': etab,
            'annee': annee,
            'aucune_affectation': True,
            'est_enseignant': est_enseignant,
        })

    if not trimestres.exists():
        messages.warning(request, "Créez d'abord les trimestres.")
        return redirect('ecoles:trimestre_generer')

    context = {
        'etablissement': etab,
        'annee': annee,
        'classes': classes_autorisees,
        'trimestres': trimestres,
        'est_enseignant': est_enseignant,
        'aucune_affectation': False,
    }
    return render(request, 'ecoles/stats_selection.html', context)


# =====================================================
# PDF — STATS COMPOSITION (Page 1)
# =====================================================
@login_required
def stats_composition_pdf(request, classe_id, trimestre_id):
    """Génère le PDF des statistiques de composition d'une classe."""
    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.error(request, "Aucune année scolaire active.")
        return redirect('ecoles:annee_creer')

    classe = get_object_or_404(Classe, id=classe_id, etablissement=etab)
    trimestre = get_object_or_404(
        Trimestre,
        id=trimestre_id,
        etablissement=etab,
        annee_scolaire=annee.libelle,
    )

    if not _verifier_acces_classe(request, classe):
        messages.error(request, f"Accès refusé à la classe '{classe.nom}'.")
        return redirect('ecoles:stats_selection')

    config, _ = ConfigurationEtablissement.objects.get_or_create(etablissement=etab)

    output = exporter_stats_composition_pdf(
        classe=classe,
        trimestre=trimestre,
        config=config,
        utilisateur=request.user,
        annee_libelle=annee.libelle,
    )

    nom_fichier = (
        f"stats_composition_{classe.nom}_{annee.libelle}_T{trimestre.numero}.pdf"
    )
    nom_fichier = nom_fichier.replace(' ', '_').replace('/', '-')

    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nom_fichier}"'
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


# =====================================================
# PDF — STATS TRIMESTRE COMPLET (Page 2)
# =====================================================
@login_required
def stats_trimestre_pdf(request, classe_id, trimestre_id):
    """Génère le PDF des statistiques complètes du trimestre."""
    from core.stats_scolaires_pdf import exporter_stats_trimestre_pdf

    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.error(request, "Aucune année scolaire active.")
        return redirect('ecoles:annee_creer')

    classe = get_object_or_404(Classe, id=classe_id, etablissement=etab)
    trimestre = get_object_or_404(
        Trimestre, id=trimestre_id,
        etablissement=etab, annee_scolaire=annee.libelle,
    )

    if not _verifier_acces_classe(request, classe):
        messages.error(request, f"Accès refusé à la classe '{classe.nom}'.")
        return redirect('ecoles:stats_selection')

    config, _ = ConfigurationEtablissement.objects.get_or_create(etablissement=etab)

    output = exporter_stats_trimestre_pdf(
        classe=classe, trimestre=trimestre, config=config,
        utilisateur=request.user, annee_libelle=annee.libelle,
    )

    nom_fichier = (
        f"stats_trimestre_{classe.nom}_{annee.libelle}_T{trimestre.numero}.pdf"
    )
    nom_fichier = nom_fichier.replace(' ', '_').replace('/', '-')

    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nom_fichier}"'
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response


# =====================================================
# PDF — STATS ANNUELLES (Page 3)
# =====================================================
@login_required
def stats_annuelles_pdf(request, classe_id):
    """Génère le PDF des statistiques annuelles d'une classe."""
    from core.stats_scolaires_pdf import exporter_stats_annuelles_pdf

    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.error(request, "Aucune année scolaire active.")
        return redirect('ecoles:annee_creer')

    classe = get_object_or_404(Classe, id=classe_id, etablissement=etab)

    if not _verifier_acces_classe(request, classe):
        messages.error(request, f"Accès refusé à la classe '{classe.nom}'.")
        return redirect('ecoles:stats_selection')

    config, _ = ConfigurationEtablissement.objects.get_or_create(etablissement=etab)

    output = exporter_stats_annuelles_pdf(
        classe=classe, annee_libelle=annee.libelle,
        config=config, utilisateur=request.user,
    )

    nom_fichier = f"stats_annuelles_{classe.nom}_{annee.libelle}.pdf"
    nom_fichier = nom_fichier.replace(' ', '_').replace('/', '-')

    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nom_fichier}"'
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response


# =====================================================
# PDF — STATS ÉTABLISSEMENT (Page 4)
# =====================================================
@login_required
def stats_etablissement_pdf(request):
    """Génère le PDF des statistiques de tout l'établissement."""
    from core.stats_scolaires_pdf import exporter_stats_etablissement_pdf

    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.error(request, "Aucune année scolaire active.")
        return redirect('ecoles:annee_creer')

    config, _ = ConfigurationEtablissement.objects.get_or_create(etablissement=etab)

    output = exporter_stats_etablissement_pdf(
        etablissement=etab, annee=annee,
        config=config, utilisateur=request.user,
    )

    nom_fichier = f"stats_etablissement_{etab.code}_{annee.libelle}.pdf"
    nom_fichier = nom_fichier.replace(' ', '_').replace('/', '-')

    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nom_fichier}"'
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response
