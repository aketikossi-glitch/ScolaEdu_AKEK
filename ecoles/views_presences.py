"""
ScolaEdu_AKEK — Vues du module Présences (Session 20).
Saisie en lot + historique par classe et par élève + statistiques.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.http import JsonResponse
from django.utils import timezone

from core.models import (
    Presence, Eleve, Classe, Inscription, AnneeScolaire,
)
from .views import (
    _get_etablissement_user, _get_enseignant_user,
    _get_classes_autorisees, _verifier_acces_classe,
)


# =====================================================
# HELPERS
# =====================================================
def _peut_saisir_presence(request):
    """Tous les rôles gestionnaires + enseignants + surveillants peuvent saisir."""
    try:
        return request.user.profil.role in (
            'chef_etablissement', 'secretaire',
            'enseignant', 'surveillant',
        )
    except Exception:
        return False


def _stats_classe_jour(classe, jour):
    """Retourne les statistiques d'une classe pour un jour donné."""
    qs = Presence.objects.filter(classe=classe, date=jour)
    return {
        'total': qs.count(),
        'present': qs.filter(statut='present').count(),
        'absent': qs.filter(statut='absent').count(),
        'retard': qs.filter(statut='retard').count(),
        'absent_justifie': qs.filter(statut='absent_justifie').count(),
    }


# =====================================================
# PAGE DE SÉLECTION
# =====================================================
@login_required
def presence_selection(request):
    """Page d'accueil : sélection classe + date pour prise de présences."""
    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    if not _peut_saisir_presence(request):
        messages.error(request, "Accès non autorisé au module Présences.")
        return redirect('dashboard:redirection')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.warning(request, "Aucune année scolaire active.")
        return redirect('ecoles:annee_creer')

    classes = list(_get_classes_autorisees(request))
    est_enseignant = _get_enseignant_user(request) is not None

    # Stats rapides du jour
    aujourdhui = date.today()
    stats_today = []
    for c in classes:
        st = _stats_classe_jour(c, aujourdhui)
        st['classe'] = c
        st['saisi'] = st['total'] > 0
        stats_today.append(st)

    context = {
        'etablissement': etab,
        'annee': annee,
        'classes': classes,
        'stats_today': stats_today,
        'aujourdhui': aujourdhui,
        'est_enseignant': est_enseignant,
    }
    return render(request, 'ecoles/presences/selection.html', context)


# =====================================================
# SAISIE DES PRÉSENCES
# =====================================================
@login_required
def presence_saisie(request):
    """Saisie en lot : présences de tous les élèves d'une classe pour une date."""
    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    if not _peut_saisir_presence(request):
        messages.error(request, "Accès non autorisé.")
        return redirect('dashboard:redirection')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.warning(request, "Aucune année scolaire active.")
        return redirect('ecoles:annee_creer')

    classe_id = request.GET.get('classe')
    date_str = request.GET.get('date')

    if not classe_id:
        messages.warning(request, "Sélectionnez une classe.")
        return redirect('ecoles:presence_selection')

    classe = get_object_or_404(Classe, id=classe_id, etablissement=etab)

    if not _verifier_acces_classe(request, classe):
        messages.error(request, f"Accès refusé à la classe '{classe.nom}'.")
        return redirect('ecoles:presence_selection')

    # Date
    try:
        jour = date.fromisoformat(date_str) if date_str else date.today()
    except Exception:
        jour = date.today()

    # Inscriptions actives
    inscriptions = Inscription.objects.filter(
        classe=classe, annee_scolaire=annee, actif=True
    ).select_related('eleve').order_by('eleve__nom', 'eleve__prenom')

    eleves = [insc.eleve for insc in inscriptions]

    if not eleves:
        messages.warning(request, "Aucun élève inscrit dans cette classe.")
        return redirect('ecoles:presence_selection')

    # Présences déjà saisies pour ce jour
    presences_existantes = {
        p.eleve_id: p
        for p in Presence.objects.filter(
            classe=classe, date=jour, eleve__in=eleves
        )
    }
    deja_saisi = len(presences_existantes) > 0

    # ===== POST : enregistrement =====
    if request.method == 'POST':
        count_saved = 0
        for eleve in eleves:
            statut = request.POST.get(f'statut_{eleve.id}', 'present').strip()
            motif = request.POST.get(f'motif_{eleve.id}', '').strip()

            if statut not in ('present', 'absent', 'retard', 'absent_justifie'):
                statut = 'present'

            Presence.objects.update_or_create(
                eleve=eleve, date=jour,
                defaults={
                    'etablissement': etab,
                    'classe': classe,
                    'statut': statut,
                    'motif': motif,
                    'saisie_par': request.user,
                }
            )
            count_saved += 1

        messages.success(
            request,
            f"✅ Présences enregistrées pour {count_saved} élève(s) le {jour.strftime('%d/%m/%Y')}."
        )
        return redirect(f"{request.path}?classe={classe.id}&date={jour.isoformat()}")

    # ===== GET : affichage =====
    eleves_data = []
    for eleve in eleves:
        p = presences_existantes.get(eleve.id)
        eleves_data.append({
            'eleve': eleve,
            'statut': p.statut if p else 'present',
            'motif': p.motif if p else '',
        })

    # Navigation date précédente / suivante
    jour_prec = jour - timedelta(days=1)
    jour_suiv = jour + timedelta(days=1)
    # Limiter au week-end (on peut laisser passer)
    today = date.today()

    context = {
        'etablissement': etab,
        'annee': annee,
        'classe': classe,
        'jour': jour,
        'jour_prec': jour_prec,
        'jour_suiv': jour_suiv,
        'aujourdhui': today,
        'eleves_data': eleves_data,
        'nb_eleves': len(eleves_data),
        'deja_saisi': deja_saisi,
        'stats': _stats_classe_jour(classe, jour) if deja_saisi else None,
        'est_enseignant': _get_enseignant_user(request) is not None,
    }
    return render(request, 'ecoles/presences/saisie.html', context)


# =====================================================
# HISTORIQUE PAR CLASSE
# =====================================================
@login_required
def presence_historique_classe(request, classe_id):
    """Historique des présences d'une classe (liste des jours de saisie)."""
    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        return redirect('ecoles:annee_creer')

    classe = get_object_or_404(Classe, id=classe_id, etablissement=etab)
    if not _verifier_acces_classe(request, classe):
        messages.error(request, f"Accès refusé à la classe '{classe.nom}'.")
        return redirect('ecoles:presence_selection')

    # Dates distinctes saisies pour cette classe
    dates = (
        Presence.objects.filter(classe=classe)
        .values_list('date', flat=True)
        .distinct()
        .order_by('-date')
    )

    # Compter par date
    jours_data = []
    for d in dates[:60]:  # 60 derniers jours max
        st = _stats_classe_jour(classe, d)
        st['date'] = d
        jours_data.append(st)

    context = {
        'etablissement': etab,
        'annee': annee,
        'classe': classe,
        'jours_data': jours_data,
        'nb_jours': len(jours_data),
    }
    return render(request, 'ecoles/presences/historique_classe.html', context)


# =====================================================
# HISTORIQUE PAR ÉLÈVE
# =====================================================
@login_required
def presence_historique_eleve(request, eleve_id):
    """Historique des présences d'un élève + statistiques."""
    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    eleve = get_object_or_404(Eleve, id=eleve_id, etablissement=etab)

    qs = Presence.objects.filter(eleve=eleve, etablissement=etab).order_by('-date')

    total = qs.count()
    present = qs.filter(statut='present').count()
    absent = qs.filter(statut='absent').count()
    retard = qs.filter(statut='retard').count()
    absent_justifie = qs.filter(statut='absent_justifie').count()

    # Taux de présence
    if total > 0:
        taux_presence = round(((present + retard) / total) * 100, 1)
    else:
        taux_presence = None

    # Inscription actuelle
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    inscription = None
    if annee:
        inscription = Inscription.objects.filter(
            eleve=eleve, annee_scolaire=annee, actif=True
        ).select_related('classe').first()

    context = {
        'etablissement': etab,
        'eleve': eleve,
        'inscription': inscription,
        'presences': qs[:100],
        'stats': {
            'total': total,
            'present': present,
            'absent': absent,
            'retard': retard,
            'absent_justifie': absent_justifie,
            'taux_presence': taux_presence,
        },
    }
    return render(request, 'ecoles/presences/historique_eleve.html', context)


# =====================================================
# RECHERCHE ÉLÈVE
# =====================================================
@login_required
def presence_recherche_eleve(request):
    """Recherche d'un élève pour voir son historique de présences."""
    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    q = request.GET.get('q', '').strip()
    eleves = Eleve.objects.none()

    if q:
        eleves = Eleve.objects.filter(
            etablissement=etab, actif=True
        ).filter(
            Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(matricule__icontains=q)
        ).order_by('nom', 'prenom')[:50]

    for e in eleves:
        e.nb_presences = Presence.objects.filter(eleve=e).count()

    context = {
        'etablissement': etab,
        'q': q,
        'eleves': eleves,
    }
    return render(request, 'ecoles/presences/recherche_eleve.html', context)


# =====================================================
# API JSON : stats d'une classe par jour (pour éventuel AJAX)
# =====================================================
@login_required
def api_stats_presence_jour(request, classe_id):
    """API JSON : stats de présence d'une classe pour une date."""
    etab = _get_etablissement_user(request)
    if not etab:
        return JsonResponse({'error': 'unauthorized'}, status=403)

    try:
        classe = Classe.objects.get(id=classe_id, etablissement=etab)
    except Classe.DoesNotExist:
        return JsonResponse({'error': 'not found'}, status=404)

    date_str = request.GET.get('date')
    try:
        jour = date.fromisoformat(date_str) if date_str else date.today()
    except Exception:
        jour = date.today()

    st = _stats_classe_jour(classe, jour)
    st['date'] = jour.isoformat()
    st['classe'] = classe.nom
    return JsonResponse(st)
