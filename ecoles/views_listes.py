"""
ScolaEdu_AKEK — Vues pour les listes de classe (Session 17).
"""
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse

from core.models import (
    AnneeScolaire, Classe, Inscription,
    ConfigurationEtablissement,
)
from core.liste_classe_pdf import exporter_liste_classe_pdf

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
def liste_selection(request):
    """Page de sélection : classe → génération de la liste PDF."""
    etab = _get_etablissement_user(request)
    if not etab:
        messages.error(request, "Aucun établissement lié à votre compte.")
        return redirect('accounts:logout')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.warning(request, "Aucune année scolaire active.")
        return redirect('ecoles:annee_creer')

    classes_autorisees = _get_classes_autorisees(request)
    est_enseignant = _get_enseignant_user(request) is not None

    # Petit plus : effectif par classe pour affichage
    classes = list(classes_autorisees)
    for c in classes:
        c.nb_inscrits = Inscription.objects.filter(classe=c, actif=True).count()

    if not classes:
        return render(request, 'ecoles/liste_selection.html', {
            'etablissement': etab,
            'annee': annee,
            'aucune_affectation': True,
            'est_enseignant': est_enseignant,
        })

    context = {
        'etablissement': etab,
        'annee': annee,
        'classes': classes,
        'est_enseignant': est_enseignant,
        'aucune_affectation': False,
    }
    return render(request, 'ecoles/liste_selection.html', context)


# =====================================================
# PDF DE LA LISTE
# =====================================================
@login_required
def liste_pdf_classe(request, classe_id):
    """Génère le PDF de la liste des élèves d'une classe."""
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
        return redirect('ecoles:liste_selection')

    inscriptions = Inscription.objects.filter(
        classe=classe, annee_scolaire=annee, actif=True
    ).count()

    if inscriptions == 0:
        messages.warning(request, "Aucun élève inscrit dans cette classe.")
        return redirect('ecoles:liste_selection')

    config, _ = ConfigurationEtablissement.objects.get_or_create(etablissement=etab)

    output = exporter_liste_classe_pdf(
        classe=classe,
        config=config,
        utilisateur=request.user,
        annee_libelle=annee.libelle,
        etablissement=etab,
    )

    nom_fichier = f"liste_{classe.nom}_{annee.libelle}.pdf"
    nom_fichier = nom_fichier.replace(' ', '_').replace('/', '-')

    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nom_fichier}"'
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


# =====================================================
# PDF DE LA LISTE DE PRÉSENCE (Session 17b)
# =====================================================
from core.liste_presence_pdf import exporter_liste_presence_pdf


@login_required
def presence_pdf_classe(request, classe_id):
    """Génère le PDF de la liste de présence vierge d'une classe."""
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
        return redirect('ecoles:liste_selection')

    inscriptions = Inscription.objects.filter(
        classe=classe, annee_scolaire=annee, actif=True
    ).count()

    if inscriptions == 0:
        messages.warning(request, "Aucun élève inscrit dans cette classe.")
        return redirect('ecoles:liste_selection')

    config, _ = ConfigurationEtablissement.objects.get_or_create(etablissement=etab)

    output = exporter_liste_presence_pdf(
        classe=classe,
        config=config,
        utilisateur=request.user,
        annee_libelle=annee.libelle,
        etablissement=etab,
    )

    nom_fichier = f"presence_{classe.nom}_{annee.libelle}.pdf"
    nom_fichier = nom_fichier.replace(' ', '_').replace('/', '-')

    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nom_fichier}"'
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response
