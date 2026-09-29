"""
ScolaEdu_AKEK — Vues Bulletins PDF.
Réutilise les helpers de ecoles/views.py + core/bulletin_pdf.py
Inclut en-têtes anti-cache pour éviter les PDFs obsolètes dans le navigateur.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse

from core.models import (
    AnneeScolaire, Trimestre, Classe, Inscription,
    Eleve, ConfigurationEtablissement,
)
from .views import (
    _get_etablissement_user,
    _get_enseignant_user,
    _get_classes_autorisees,
    _verifier_acces_classe,
)


# =====================================================
# HELPERS INTERNES BULLETINS
# =====================================================
def _get_trimestres_autorises(etab, annee):
    """Trimestres de l'année en cours pour l'établissement."""
    return Trimestre.objects.filter(
        etablissement=etab,
        annee_scolaire=annee.libelle
    ).order_by('numero')


def _get_inscriptions_classe(classe, annee):
    """Inscriptions actives de la classe pour l'année en cours."""
    return Inscription.objects.filter(
        classe=classe,
        annee_scolaire=annee,
        actif=True,
    ).select_related('eleve').order_by('eleve__nom', 'eleve__prenom')


def _classes_titulaire(request):
    """
    Retourne les classes où l'utilisateur peut imprimer les bulletins :
      - Enseignant : uniquement les classes où il est TITULAIRE
      - Chef/secrétaire : TOUTES les classes
    """
    etab = _get_etablissement_user(request)
    if not etab:
        return Classe.objects.none()

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        return Classe.objects.none()

    enseignant = _get_enseignant_user(request)
    if enseignant:
        return Classe.objects.filter(
            etablissement=etab,
            annee_scolaire=annee,
            titulaire=enseignant,
        ).order_by('niveau', 'nom')

    return Classe.objects.filter(
        etablissement=etab,
        annee_scolaire=annee,
    ).order_by('niveau', 'nom')


def _est_titulaire_de(request, classe):
    """
    Vérifie que l'utilisateur peut imprimer les bulletins de cette classe.
      - Chef/secrétaire : toujours autorisé
      - Enseignant : seulement s'il est titulaire de la classe
    """
    enseignant = _get_enseignant_user(request)
    if not enseignant:
        return True
    return classe.titulaire_id == enseignant.id


def _reponse_pdf_anti_cache(output, nom_fichier):
    """
    ✅ Retourne une HttpResponse PDF AVEC en-têtes anti-cache.
    Empêche le navigateur de servir un ancien PDF depuis son cache.
    """
    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nom_fichier}"'
    # ✅ Ces 3 en-têtes forcent le navigateur à TOUJOURS recharger
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


# =====================================================
# SÉLECTION
# =====================================================
@login_required
def bulletin_selection(request):
    """Page de sélection : classe + trimestre + génération."""
    etab = _get_etablissement_user(request)
    if not etab:
        messages.error(request, "Aucun établissement lié à votre compte.")
        return redirect('accounts:logout')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.warning(request, "Aucune année scolaire active.")
        return redirect('ecoles:annee_creer')

    # ✅ Enseignant : uniquement classes où il est titulaire
    classes_autorisees = _classes_titulaire(request)
    trimestres = _get_trimestres_autorises(etab, annee)
    est_enseignant = _get_enseignant_user(request) is not None

    if not classes_autorisees.exists():
        return render(request, 'ecoles/bulletin_selection.html', {
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
    return render(request, 'ecoles/bulletin_selection.html', context)


# =====================================================
# PDF — UN ÉLÈVE
# =====================================================
@login_required
def bulletin_pdf_eleve(request, eleve_id, trimestre_id):
    """Génère le bulletin PDF d'un élève."""
    from core.bulletin_pdf import (
        exporter_bulletins_pdf,
        _calculer_bulletin_eleve,
        _calculer_classement,
    )

    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.error(request, "Aucune année scolaire active.")
        return redirect('ecoles:annee_creer')

    eleve = get_object_or_404(Eleve, id=eleve_id, etablissement=etab)

    # ✅ SÉCURITÉ : on force le trimestre à appartenir à l'année en cours
    trimestre = get_object_or_404(
        Trimestre,
        id=trimestre_id,
        etablissement=etab,
        annee_scolaire=annee.libelle,
    )

    inscription = Inscription.objects.filter(
        eleve=eleve, annee_scolaire=annee, actif=True
    ).select_related('classe').first()

    if not inscription:
        messages.error(request, f"{eleve.nom_complet} n'est pas inscrit(e) cette année.")
        return redirect('ecoles:bulletin_selection')

    classe = inscription.classe

    if not _est_titulaire_de(request, classe):
        messages.error(
            request,
            f"Accès refusé : vous devez être titulaire de la classe '{classe.nom}' pour imprimer les bulletins."
        )
        return redirect('ecoles:bulletin_selection')

    bulletin = _calculer_bulletin_eleve(eleve, classe, trimestre)
    inscriptions = list(_get_inscriptions_classe(classe, annee))
    classement, stats = _calculer_classement(classe, trimestre, inscriptions)
    rang = classement.get(eleve.id, {}).get('rang')
    effectif = stats.get('effectif', 0)

    config, _ = ConfigurationEtablissement.objects.get_or_create(etablissement=etab)

    bulletins_data = [{
        'eleve': eleve,
        'classe': classe,
        'trimestre': trimestre,
        'bulletin': bulletin,
        'rang': rang,
        'effectif': effectif,
        'stats': stats,
        'inscriptions': inscriptions,
    }]

    output = exporter_bulletins_pdf(
        bulletins_data, config=config, utilisateur=request.user, mode_lot=False
    )

    nom_fichier = f"bulletin_{eleve.matricule}_{trimestre.annee_scolaire}_T{trimestre.numero}.pdf"
    # ✅ Utilise le helper anti-cache
    return _reponse_pdf_anti_cache(output, nom_fichier)


# =====================================================
# PDF — TOUTE LA CLASSE
# =====================================================
@login_required
def bulletin_pdf_classe(request, classe_id, trimestre_id):
    """Génère UN PDF avec tous les bulletins de la classe."""
    from core.bulletin_pdf import (
        exporter_bulletins_pdf,
        _calculer_bulletin_eleve,
        _calculer_classement,
    )

    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.error(request, "Aucune année scolaire active.")
        return redirect('ecoles:annee_creer')

    classe = get_object_or_404(Classe, id=classe_id, etablissement=etab)

    # ✅ SÉCURITÉ : on force le trimestre à appartenir à l'année en cours
    trimestre = get_object_or_404(
        Trimestre,
        id=trimestre_id,
        etablissement=etab,
        annee_scolaire=annee.libelle,
    )

    if not _est_titulaire_de(request, classe):
        messages.error(
            request,
            f"Accès refusé : vous devez être titulaire de la classe '{classe.nom}' pour imprimer les bulletins."
        )
        return redirect('ecoles:bulletin_selection')

    inscriptions = list(_get_inscriptions_classe(classe, annee))
    if not inscriptions:
        messages.warning(request, "Aucun élève inscrit dans cette classe.")
        return redirect('ecoles:bulletin_selection')

    classement, stats = _calculer_classement(classe, trimestre, inscriptions)

    bulletins_data = []
    for insc in inscriptions:
        eleve = insc.eleve
        bulletin = _calculer_bulletin_eleve(eleve, classe, trimestre)
        bulletins_data.append({
            'eleve': eleve,
            'classe': classe,
            'trimestre': trimestre,
            'bulletin': bulletin,
            'rang': classement.get(eleve.id, {}).get('rang'),
            'effectif': stats.get('effectif', 0),
            'stats': stats,
            'inscriptions': inscriptions,
        })

    config, _ = ConfigurationEtablissement.objects.get_or_create(etablissement=etab)

    output = exporter_bulletins_pdf(
        bulletins_data, config=config, utilisateur=request.user, mode_lot=True
    )

    nom_fichier = f"bulletins_{classe.nom}_{trimestre.annee_scolaire}_T{trimestre.numero}.pdf"
    nom_fichier = nom_fichier.replace(' ', '_').replace('/', '-')
    # ✅ Utilise le helper anti-cache
    return _reponse_pdf_anti_cache(output, nom_fichier)
