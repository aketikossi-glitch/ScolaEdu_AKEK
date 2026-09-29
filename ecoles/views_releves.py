"""
ScolaEdu_AKEK — Vues pour le relevé de notes de classe (Session 2).
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
from core.releve_classe_pdf import exporter_releve_classe_pdf

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
def releve_selection(request):
    """Page de sélection : classe + trimestre + génération du relevé."""
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
        return render(request, 'ecoles/releve_selection.html', {
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
    return render(request, 'ecoles/releve_selection.html', context)


# =====================================================
# PDF DU RELEVÉ
# =====================================================
@login_required
def releve_pdf_classe(request, classe_id, trimestre_id):
    """Génère le PDF du relevé de notes d'une classe pour un trimestre."""
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
        return redirect('ecoles:releve_selection')

    inscriptions = Inscription.objects.filter(
        classe=classe, annee_scolaire=annee, actif=True
    ).count()

    if inscriptions == 0:
        messages.warning(request, "Aucun élève inscrit dans cette classe.")
        return redirect('ecoles:releve_selection')

    config, _ = ConfigurationEtablissement.objects.get_or_create(etablissement=etab)

    output = exporter_releve_classe_pdf(
        classe=classe,
        trimestre=trimestre,
        config=config,
        utilisateur=request.user,
        annee_libelle=annee.libelle,
        etablissement=etab,
    )

    nom_fichier = (
        f"releve_{classe.nom}_{annee.libelle}_T{trimestre.numero}.pdf"
    )
    nom_fichier = nom_fichier.replace(' ', '_').replace('/', '-')

    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nom_fichier}"'
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response
