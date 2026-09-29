"""
ScolaEdu_AKEK — Vues pour les cartes scolaires (Session 10).
"""
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q

from core.models import (
    AnneeScolaire, Classe, Inscription, Eleve,
    ConfigurationEtablissement,
)
from core.carte_scolaire_pdf import exporter_cartes_scolaires_pdf


# =====================================================
# HELPERS
# =====================================================
def _get_etablissement_user(request):
    try:
        return request.user.profil.etablissement
    except Exception:
        return None


def _role_autorise(request):
    """Chef, secrétaire ou admin principal peuvent générer des cartes."""
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
def carte_selection(request):
    """Page de sélection : classe entière ou élève individuel."""
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

    classes = Classe.objects.filter(
        etablissement=etab, annee_scolaire=annee
    ).order_by('niveau', 'nom')

    for c in classes:
        c.nb_inscrits = Inscription.objects.filter(
            classe=c, annee_scolaire=annee, actif=True
        ).count()

    # Recherche élève individuel
    recherche = request.GET.get('q', '').strip()
    eleves_recherche = []
    if recherche:
        eleves_recherche = Eleve.objects.filter(
            etablissement=etab,
            inscriptions__annee_scolaire=annee,
            inscriptions__actif=True,
        ).filter(
            Q(nom__icontains=recherche) |
            Q(prenom__icontains=recherche) |
            Q(matricule__icontains=recherche)
        ).distinct().order_by('nom', 'prenom')[:30]

    # Marquer les élèves ayant une photo (utile pour signaler)
    for e in eleves_recherche:
        e.a_photo = bool(e.photo)

    config = ConfigurationEtablissement.objects.filter(etablissement=etab).first()

    # Élèves sans photo (avertissement utile)
    nb_sans_photo = Eleve.objects.filter(
        etablissement=etab,
        inscriptions__annee_scolaire=annee,
        inscriptions__actif=True,
        photo='',
    ).distinct().count()

    context = {
        'etablissement': etab,
        'annee': annee,
        'classes': classes,
        'eleves_recherche': eleves_recherche,
        'recherche': recherche,
        'config': config,
        'config_complete': bool(config and config.nom_chef and config.cachet_ecole),
        'nb_sans_photo': nb_sans_photo,
        'total_inscrits': Inscription.objects.filter(
            annee_scolaire=annee, classe__etablissement=etab, actif=True
        ).count(),
    }
    return render(request, 'ecoles/carte_selection.html', context)


# =====================================================
# PDF PAR CLASSE
# =====================================================
@login_required
def carte_pdf_classe(request, classe_id):
    if not _role_autorise(request):
        messages.error(request, "Accès non autorisé.")
        return redirect('dashboard:redirection')

    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('accounts:logout')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.warning(request, "Aucune année scolaire active.")
        return redirect('ecoles:annee_creer')

    classe = get_object_or_404(Classe, id=classe_id, etablissement=etab)

    inscriptions = Inscription.objects.filter(
        classe=classe, annee_scolaire=annee, actif=True
    ).select_related('eleve').order_by('eleve__nom', 'eleve__prenom')

    if not inscriptions.exists():
        messages.warning(request, f"Aucun élève inscrit en {classe.nom}.")
        return redirect('ecoles:carte_selection')

    eleves_data = [
        {'eleve': insc.eleve, 'classe': classe}
        for insc in inscriptions
    ]

    config = ConfigurationEtablissement.objects.filter(etablissement=etab).first()

    output = exporter_cartes_scolaires_pdf(
        eleves_data, annee.libelle, config=config, utilisateur=request.user
    )

    nom_fichier = (
        f"cartes_{etab.code}_{classe.nom.replace(' ', '_')}_"
        f"{annee.libelle}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    )
    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return response


# =====================================================
# PDF PAR ÉLÈVE (individuel)
# =====================================================
@login_required
def carte_pdf_eleve(request, eleve_id):
    if not _role_autorise(request):
        messages.error(request, "Accès non autorisé.")
        return redirect('dashboard:redirection')

    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('accounts:logout')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.warning(request, "Aucune année scolaire active.")
        return redirect('ecoles:annee_creer')

    eleve = get_object_or_404(Eleve, id=eleve_id, etablissement=etab)

    inscription = Inscription.objects.filter(
        eleve=eleve, annee_scolaire=annee, actif=True
    ).select_related('classe').first()

    if not inscription:
        messages.warning(
            request,
            f"{eleve.nom_complet} n'est pas inscrit(e) pour {annee.libelle}."
        )
        return redirect('ecoles:carte_selection')

    eleves_data = [{'eleve': eleve, 'classe': inscription.classe}]
    config = ConfigurationEtablissement.objects.filter(etablissement=etab).first()

    output = exporter_cartes_scolaires_pdf(
        eleves_data, annee.libelle, config=config, utilisateur=request.user
    )

    nom_fichier = (
        f"carte_{etab.code}_{eleve.matricule}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    )
    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return response
