"""
ScolaEdu_AKEK — Vues pour les attestations PDF (Session 3).
"""
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse

from core.models import (
    AnneeScolaire, Classe, Inscription, Eleve,
    ConfigurationEtablissement,
)
from core.attestations_pdf import (
    exporter_attestation_pdf,
    TYPES_ATTESTATIONS,
)

from .views import _get_etablissement_user


def _role_autorise(request):
    try:
        return request.user.profil.role in (
            'chef_etablissement', 'secretaire', 'admin_principal'
        )
    except Exception:
        return False


# =====================================================
# PAGE DE SÉLECTION
# =====================================================
@login_required
def attestation_selection(request):
    """Page de sélection : élève + type d'attestation."""
    if not _role_autorise(request):
        messages.error(request, "Accès non autorisé.")
        return redirect('dashboard:redirection')

    etab = _get_etablissement_user(request)
    if not etab:
        messages.error(request, "Aucun établissement lié à votre compte.")
        return redirect('accounts:logout')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.warning(request, "Aucune année scolaire active.")
        return redirect('ecoles:annee_creer')

    # Élèves inscrits cette année
    inscriptions = Inscription.objects.filter(
        annee_scolaire=annee,
        classe__etablissement=etab,
        actif=True,
    ).select_related('eleve', 'classe').order_by('eleve__nom', 'eleve__prenom')

    # Recherche élève
    recherche = request.GET.get('q', '').strip()
    if recherche:
        inscriptions = inscriptions.filter(
            eleve__nom__icontains=recherche
        ) | inscriptions.filter(
            eleve__prenom__icontains=recherche
        ) | inscriptions.filter(
            eleve__matricule__icontains=recherche
        )

    context = {
        'etablissement': etab,
        'annee': annee,
        'inscriptions': inscriptions,
        'recherche': recherche,
        'types': TYPES_ATTESTATIONS,
        'total': inscriptions.count(),
    }
    return render(request, 'ecoles/attestation_selection.html', context)


# =====================================================
# PDF ATTESTATION
# =====================================================
@login_required
def attestation_pdf(request, eleve_id, type_attestation):
    """Génère une attestation PDF pour un élève."""
    if not _role_autorise(request):
        messages.error(request, "Accès non autorisé.")
        return redirect('dashboard:redirection')

    if type_attestation not in TYPES_ATTESTATIONS:
        messages.error(request, "Type d'attestation inconnu.")
        return redirect('ecoles:attestation_selection')

    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('accounts:logout')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.error(request, "Aucune année scolaire active.")
        return redirect('ecoles:annee_creer')

    eleve = get_object_or_404(Eleve, id=eleve_id, etablissement=etab)

    inscription = Inscription.objects.filter(
        eleve=eleve, annee_scolaire=annee, actif=True
    ).select_related('classe').first()

    if not inscription:
        messages.warning(
            request,
            f"{eleve.nom_complet} n'est pas inscrit(e) pour l'année {annee.libelle}."
        )
        return redirect('ecoles:attestation_selection')

    config, _ = ConfigurationEtablissement.objects.get_or_create(etablissement=etab)

    # Motif de radiation (optionnel)
    motif_radiation = request.GET.get('motif', '').strip() or None

    output = exporter_attestation_pdf(
        eleve=eleve,
        type_attestation=type_attestation,
        inscription=inscription,
        annee=annee,
        etablissement=etab,
        config=config,
        utilisateur=request.user,
        motif_radiation=motif_radiation,
    )

    nom_fichier = (
        f"attestation_{type_attestation}_{etab.code}_{eleve.matricule}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    )
    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nom_fichier}"'
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response
