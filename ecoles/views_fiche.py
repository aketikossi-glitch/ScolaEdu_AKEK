"""
ScolaEdu_AKEK — Vues pour les fiches PDF (élève + vierge).
"""
from datetime import datetime

from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse

from core.models import Eleve, AnneeScolaire, ConfigurationEtablissement
from core.fiche_eleve_pdf import exporter_fiche_eleve_pdf
from core.fiche_vierge_pdf import exporter_fiche_vierge_pdf


def _get_etablissement_user(request):
    try:
        return request.user.profil.etablissement
    except Exception:
        return None


def _role_autorise(request):
    try:
        return request.user.profil.role in (
            'chef_etablissement', 'secretaire', 'admin_principal'
        )
    except Exception:
        return False


@login_required
def eleve_fiche_pdf(request, eleve_id):
    """Fiche élève remplie."""
    if not _role_autorise(request):
        messages.error(request, "Accès non autorisé.")
        return redirect('dashboard:redirection')

    etab = _get_etablissement_user(request)
    if not etab:
        messages.error(request, "Aucun établissement lié à votre compte.")
        return redirect('accounts:logout')

    eleve = get_object_or_404(Eleve, id=eleve_id, etablissement=etab)
    config = ConfigurationEtablissement.objects.filter(etablissement=etab).first()
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    annee_libelle = annee.libelle if annee else None

    output = exporter_fiche_eleve_pdf(
        eleve=eleve, config=config, utilisateur=request.user,
        annee_courante=annee_libelle,
    )

    nom_fichier = (
        f"fiche_{etab.code}_{eleve.matricule}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    )
    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return response


@login_required
def eleve_fiche_vierge_pdf(request):
    """Fiche vierge à imprimer pour les inscriptions."""
    if not _role_autorise(request):
        messages.error(request, "Accès non autorisé.")
        return redirect('dashboard:redirection')

    etab = _get_etablissement_user(request)
    if not etab:
        messages.error(request, "Aucun établissement lié à votre compte.")
        return redirect('accounts:logout')

    config = ConfigurationEtablissement.objects.filter(etablissement=etab).first()
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    annee_libelle = annee.libelle if annee else None

    output = exporter_fiche_vierge_pdf(
        etablissement=etab, config=config,
        utilisateur=request.user, annee_courante=annee_libelle,
    )

    nom_fichier = (
        f"fiche_vierge_{etab.code}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    )
    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return response


# =====================================================
# FICHE PRÉ-REMPLIE (à vérifier par le parent)
# =====================================================
@login_required
def eleve_fiche_preremplie_pdf(request, eleve_id):
    """Fiche pré-remplie avec les données de l'élève."""
    from core.fiche_preremplie_pdf import exporter_fiche_preremplie_pdf

    if not _role_autorise(request):
        messages.error(request, "Accès non autorisé.")
        return redirect('dashboard:redirection')

    etab = _get_etablissement_user(request)
    if not etab:
        messages.error(request, "Aucun établissement lié à votre compte.")
        return redirect('accounts:logout')

    eleve = get_object_or_404(Eleve, id=eleve_id, etablissement=etab)
    config = ConfigurationEtablissement.objects.filter(etablissement=etab).first()
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    annee_libelle = annee.libelle if annee else None

    output = exporter_fiche_preremplie_pdf(
        eleve=eleve, config=config, utilisateur=request.user,
        annee_courante=annee_libelle,
    )

    nom_fichier = (
        f"fiche_preremplie_{etab.code}_{eleve.matricule}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    )
    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return response
