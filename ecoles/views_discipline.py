"""
ScolaEdu_AKEK — Vues du module Discipline (Session 18).
Signalements d'incidents + sanctions + historique par élève.
Version 2 : sélection en 2 étapes (classe → élève) via API JSON.
"""
from datetime import date

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.http import JsonResponse

from core.models import (
    Eleve, IncidentDisciplinaire, Sanction,
    AnneeScolaire, Inscription, Classe,
)
from .forms_discipline import IncidentForm, SanctionForm
from .views import _get_etablissement_user, _get_enseignant_user


# =====================================================
# HELPERS LOCAUX
# =====================================================
def _peut_signaler(request):
    """Tous les rôles sauf admin_principal peuvent signaler."""
    try:
        return request.user.profil.role in (
            'chef_etablissement', 'secretaire', 'enseignant', 'surveillant'
        )
    except Exception:
        return False


def _peut_sanctionner(request):
    """Seuls chef_etablissement et surveillant peuvent sanctionner."""
    try:
        return request.user.profil.role in ('chef_etablissement', 'surveillant')
    except Exception:
        return False


def _classes_etablissement(etab):
    """Liste des classes de l'année en cours pour cet établissement."""
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        return []
    return list(
        Classe.objects.filter(etablissement=etab, annee_scolaire=annee)
        .order_by('niveau', 'nom')
    )


# =====================================================
# MENU PRINCIPAL
# =====================================================
@login_required
def discipline_menu(request):
    """Page d'accueil du module Discipline."""
    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    if not _peut_signaler(request):
        messages.error(request, "Accès non autorisé au module Discipline.")
        return redirect('dashboard:redirection')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()

    qs_incidents = IncidentDisciplinaire.objects.filter(etablissement=etab)
    qs_sanctions = Sanction.objects.filter(etablissement=etab)

    if annee:
        qs_incidents = qs_incidents.filter(date_incident__year__gte=annee.date_debut.year)
        qs_sanctions = qs_sanctions.filter(date_debut__year__gte=annee.date_debut.year)

    stats = {
        'nb_total': qs_incidents.count(),
        'nb_signale': qs_incidents.filter(statut='signale').count(),
        'nb_traite': qs_incidents.filter(statut='traite').count(),
        'nb_grave': qs_incidents.filter(gravite='grave').count(),
        'nb_sanctions': qs_sanctions.count(),
    }

    derniers_incidents = (
        qs_incidents.select_related('eleve', 'signale_par')
        .order_by('-date_signalement')[:5]
    )

    context = {
        'etablissement': etab,
        'annee': annee,
        'stats': stats,
        'derniers_incidents': derniers_incidents,
        'peut_signaler': _peut_signaler(request),
        'peut_sanctionner': _peut_sanctionner(request),
    }
    return render(request, 'ecoles/discipline/menu.html', context)


# =====================================================
# LISTE DES INCIDENTS
# =====================================================
@login_required
def incident_liste(request):
    """Liste des incidents avec filtres."""
    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    qs = IncidentDisciplinaire.objects.filter(etablissement=etab)\
        .select_related('eleve', 'signale_par')

    f_statut = request.GET.get('statut', '').strip()
    f_gravite = request.GET.get('gravite', '').strip()
    f_type = request.GET.get('type', '').strip()
    f_recherche = request.GET.get('q', '').strip()

    if f_statut:
        qs = qs.filter(statut=f_statut)
    if f_gravite:
        qs = qs.filter(gravite=f_gravite)
    if f_type:
        qs = qs.filter(type_incident=f_type)
    if f_recherche:
        qs = qs.filter(
            Q(eleve__nom__icontains=f_recherche) |
            Q(eleve__prenom__icontains=f_recherche) |
            Q(eleve__matricule__icontains=f_recherche)
        )

    qs = qs.order_by('-date_incident', '-date_signalement')

    total = qs.count()
    nb_signale = qs.filter(statut='signale').count()
    nb_traite = qs.filter(statut='traite').count()
    nb_classe = qs.filter(statut='classe').count()

    context = {
        'etablissement': etab,
        'incidents': qs,
        'total': total,
        'nb_signale': nb_signale,
        'nb_traite': nb_traite,
        'nb_classe': nb_classe,
        'f_statut': f_statut,
        'f_gravite': f_gravite,
        'f_type': f_type,
        'f_recherche': f_recherche,
        'types_incident': IncidentDisciplinaire.TYPE_CHOICES,
        'gravites': IncidentDisciplinaire.GRAVITE_CHOICES,
        'statuts': IncidentDisciplinaire.STATUT_CHOICES,
        'peut_sanctionner': _peut_sanctionner(request),
    }
    return render(request, 'ecoles/discipline/incident_liste.html', context)


# =====================================================
# API JSON : élèves d'une classe
# =====================================================
@login_required
def api_eleves_par_classe(request, classe_id):
    """API JSON : liste des élèves actifs d'une classe (pour le formulaire incident)."""
    etab = _get_etablissement_user(request)
    if not etab:
        return JsonResponse({'eleves': []}, status=403)

    try:
        classe = Classe.objects.get(id=classe_id, etablissement=etab)
    except Classe.DoesNotExist:
        return JsonResponse({'eleves': []}, status=404)

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        return JsonResponse({'eleves': []})

    inscriptions = (
        Inscription.objects.filter(
            classe=classe, annee_scolaire=annee, actif=True
        )
        .select_related('eleve')
        .order_by('eleve__nom', 'eleve__prenom')
    )

    eleves = [
        {
            'id': insc.eleve.id,
            'nom_complet': insc.eleve.nom_complet,
            'matricule': insc.eleve.matricule,
        }
        for insc in inscriptions
    ]
    return JsonResponse({'eleves': eleves})


# =====================================================
# CRÉER UN INCIDENT
# =====================================================
@login_required
def incident_creer(request):
    """Créer un nouveau signalement d'incident."""
    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    if not _peut_signaler(request):
        messages.error(request, "Vous n'êtes pas autorisé à signaler un incident.")
        return redirect('ecoles:discipline_menu')

    eleve_id = request.GET.get('eleve')
    eleve_initial = None
    classe_initial_id = None
    if eleve_id:
        try:
            eleve_initial = Eleve.objects.get(id=eleve_id, etablissement=etab)
            # Retrouver sa classe (inscription active)
            annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
            if annee:
                insc = Inscription.objects.filter(
                    eleve=eleve_initial, annee_scolaire=annee, actif=True
                ).select_related('classe').first()
                if insc and insc.classe:
                    classe_initial_id = insc.classe.id
        except Eleve.DoesNotExist:
            pass

    if request.method == 'POST':
        form = IncidentForm(
            request.POST,
            etablissement=etab,
            eleve_initial=eleve_initial,
            classe_initial=classe_initial_id,
        )
        if form.is_valid():
            incident = form.save(commit=False)
            incident.etablissement = etab
            incident.signale_par = request.user
            incident.save()
            messages.success(
                request,
                f"✅ Incident signalé pour {incident.eleve.nom_complet}."
            )
            return redirect('ecoles:incident_detail', incident_id=incident.id)
    else:
        form = IncidentForm(
            etablissement=etab,
            eleve_initial=eleve_initial,
            classe_initial=classe_initial_id,
            initial={'date_incident': date.today()},
        )

    context = {
        'etablissement': etab,
        'form': form,
        'titre': 'Signaler un incident',
        'mode': 'creer',
    }
    return render(request, 'ecoles/discipline/incident_form.html', context)


# =====================================================
# MODIFIER UN INCIDENT
# =====================================================
@login_required
def incident_modifier(request, incident_id):
    """Modifier un incident existant."""
    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    incident = get_object_or_404(
        IncidentDisciplinaire, id=incident_id, etablissement=etab
    )

    # Retrouver la classe actuelle de l'élève (pour pré-remplir le select)
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    classe_initial_id = None
    if annee:
        insc = Inscription.objects.filter(
            eleve=incident.eleve, annee_scolaire=annee, actif=True
        ).select_related('classe').first()
        if insc and insc.classe:
            classe_initial_id = insc.classe.id

    if request.method == 'POST':
        form = IncidentForm(
            request.POST,
            instance=incident,
            etablissement=etab,
            classe_initial=classe_initial_id,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Incident modifié.")
            return redirect('ecoles:incident_detail', incident_id=incident.id)
    else:
        form = IncidentForm(
            instance=incident,
            etablissement=etab,
            classe_initial=classe_initial_id,
        )

    context = {
        'etablissement': etab,
        'form': form,
        'incident': incident,
        'titre': 'Modifier un incident',
        'mode': 'modifier',
    }
    return render(request, 'ecoles/discipline/incident_form.html', context)


# =====================================================
# DÉTAIL D'UN INCIDENT
# =====================================================
@login_required
def incident_detail(request, incident_id):
    """Vue détaillée d'un incident + ses sanctions."""
    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    incident = get_object_or_404(
        IncidentDisciplinaire.objects.select_related('eleve', 'signale_par'),
        id=incident_id, etablissement=etab
    )

    sanctions = incident.sanctions.select_related('decidee_par').all()

    context = {
        'etablissement': etab,
        'incident': incident,
        'sanctions': sanctions,
        'peut_sanctionner': _peut_sanctionner(request),
    }
    return render(request, 'ecoles/discipline/incident_detail.html', context)


# =====================================================
# SUPPRIMER UN INCIDENT
# =====================================================
@login_required
def incident_supprimer(request, incident_id):
    """Supprimer un incident (avec confirmation)."""
    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    if not _peut_sanctionner(request):
        messages.error(request, "Vous n'êtes pas autorisé à supprimer un incident.")
        return redirect('ecoles:discipline_menu')

    incident = get_object_or_404(
        IncidentDisciplinaire, id=incident_id, etablissement=etab
    )

    if request.method == 'POST':
        eleve_nom = incident.eleve.nom_complet
        incident.delete()
        messages.success(request, f"🗑️ Incident de {eleve_nom} supprimé.")
        return redirect('ecoles:incident_liste')

    context = {
        'etablissement': etab,
        'incident': incident,
    }
    return render(request, 'ecoles/discipline/incident_supprimer.html', context)


# =====================================================
# CRÉER UNE SANCTION
# =====================================================
@login_required
def sanction_creer(request, incident_id):
    """Créer une sanction liée à un incident."""
    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    if not _peut_sanctionner(request):
        messages.error(request, "Vous n'êtes pas autorisé à décider une sanction.")
        return redirect('ecoles:discipline_menu')

    incident = get_object_or_404(
        IncidentDisciplinaire, id=incident_id, etablissement=etab
    )

    if request.method == 'POST':
        form = SanctionForm(request.POST)
        if form.is_valid():
            sanction = form.save(commit=False)
            sanction.etablissement = etab
            sanction.incident = incident
            sanction.eleve = incident.eleve
            sanction.decidee_par = request.user
            sanction.save()

            if incident.statut == 'signale':
                incident.statut = 'traite'
                incident.save(update_fields=['statut'])

            messages.success(
                request,
                f"✅ Sanction enregistrée pour {incident.eleve.nom_complet}."
            )
            return redirect('ecoles:incident_detail', incident_id=incident.id)
    else:
        form = SanctionForm(initial={'date_debut': date.today()})

    context = {
        'etablissement': etab,
        'form': form,
        'incident': incident,
        'titre': f"Décider une sanction — {incident.eleve.nom_complet}",
    }
    return render(request, 'ecoles/discipline/sanction_form.html', context)


# =====================================================
# SUPPRIMER UNE SANCTION
# =====================================================
@login_required
def sanction_supprimer(request, sanction_id):
    """Supprimer une sanction."""
    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    if not _peut_sanctionner(request):
        messages.error(request, "Vous n'êtes pas autorisé.")
        return redirect('ecoles:discipline_menu')

    sanction = get_object_or_404(
        Sanction, id=sanction_id, etablissement=etab
    )
    incident_id = sanction.incident_id

    if request.method == 'POST':
        sanction.delete()
        messages.success(request, "🗑️ Sanction supprimée.")
        return redirect('ecoles:incident_detail', incident_id=incident_id)

    context = {
        'etablissement': etab,
        'sanction': sanction,
    }
    return render(request, 'ecoles/discipline/sanction_supprimer.html', context)


# =====================================================
# HISTORIQUE PAR ÉLÈVE
# =====================================================
@login_required
def eleve_historique(request, eleve_id):
    """Historique disciplinaire complet d'un élève."""
    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    eleve = get_object_or_404(Eleve, id=eleve_id, etablissement=etab)

    incidents = IncidentDisciplinaire.objects.filter(
        etablissement=etab, eleve=eleve
    ).select_related('signale_par').order_by('-date_incident')

    sanctions = Sanction.objects.filter(
        etablissement=etab, eleve=eleve
    ).select_related('decidee_par', 'incident').order_by('-date_debut')

    stats = {
        'nb_incidents': incidents.count(),
        'nb_graves': incidents.filter(gravite='grave').count(),
        'nb_sanctions': sanctions.count(),
    }

    context = {
        'etablissement': etab,
        'eleve': eleve,
        'incidents': incidents,
        'sanctions': sanctions,
        'stats': stats,
    }
    return render(request, 'ecoles/discipline/eleve_historique.html', context)


# =====================================================
# RECHERCHE D'ÉLÈVE POUR HISTORIQUE
# =====================================================
@login_required
def eleve_recherche(request):
    """Recherche d'un élève pour consulter son historique disciplinaire."""
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
        e.nb_incidents_aff = IncidentDisciplinaire.objects.filter(
            etablissement=etab, eleve=e
        ).count()

    context = {
        'etablissement': etab,
        'q': q,
        'eleves': eleves,
    }
    return render(request, 'ecoles/discipline/eleve_recherche.html', context)
