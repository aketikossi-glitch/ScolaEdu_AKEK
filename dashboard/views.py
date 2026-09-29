"""
ScolaEdu_AKEK — Vues du dashboard.
Version 2 (Session 22) :
  - Stats enrichies (taux admission, admis/actifs, notes saisies)
  - Top 6 des meilleures moyennes du trimestre en cours
  - Effectif par classe avec link
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.db.models import Avg, Count, Q

from core.models import (
    Etablissement, Eleve, Classe, Enseignant, Note, Trimestre,
    AnneeScolaire, Inscription, MatiereClasse,
)


# =====================================================
# REDIRECTION PAR RÔLE
# =====================================================
@login_required
def redirection(request):
    """Redirige l'utilisateur vers la bonne interface selon son rôle."""
    try:
        role = request.user.profil.role
    except Exception:
        messages.error(request, "Votre compte n'a pas de profil. Contactez l'administrateur.")
        return redirect('accounts:logout')

    if role == 'admin_principal':
        return redirect('dashboard:admin_principal')
    elif role == 'chef_etablissement':
        return redirect('dashboard:chef_etablissement')
    elif role == 'secretaire':
        return redirect('dashboard:chef_etablissement')
    elif role == 'enseignant':
        return redirect('dashboard:enseignant_dashboard')
    elif role == 'comptable':
        messages.warning(request, "L'interface comptable est en cours de développement.")
        return redirect('accounts:logout')
    elif role == 'surveillant':
        messages.warning(request, "L'interface surveillant est en cours de développement.")
        return redirect('accounts:logout')
    else:
        messages.warning(request, f"Le rôle '{role}' n'a pas encore d'interface.")
        return redirect('accounts:logout')


# =====================================================
# ADMIN PRINCIPAL
# =====================================================
@login_required
def admin_principal(request):
    if request.user.profil.role != 'admin_principal':
        return redirect('dashboard:redirection')

    context = {
        'titre': 'Administration centrale',
        'nb_etablissements': Etablissement.objects.count(),
        'nb_etablissements_actifs': Etablissement.objects.filter(actif=True).count(),
        'etablissements': Etablissement.objects.all().order_by('-date_creation')[:5],
    }
    return render(request, 'dashboard/admin_principal.html', context)


# =====================================================
# CHEF D'ÉTABLISSEMENT (Session 22 — enrichi)
# =====================================================
@login_required
def chef_etablissement(request):
    """Tableau de bord filtré par l'année scolaire active."""
    if request.user.profil.role not in ('chef_etablissement', 'secretaire'):
        return redirect('dashboard:redirection')

    etab = request.user.profil.etablissement
    if not etab:
        messages.error(request, "Aucun établissement lié à votre compte.")
        return redirect('accounts:logout')

    annee_courante = AnneeScolaire.objects.filter(
        etablissement=etab, en_cours=True
    ).first()

    annees_disponibles = AnneeScolaire.objects.filter(
        etablissement=etab
    ).order_by('-libelle')

    # Valeurs par défaut
    nb_eleves = nb_garcons = nb_filles = nb_classes = nb_enseignants = 0
    moyenne_generale = 0
    effectif_par_classe = []
    trimestre_courant = None
    nb_notes_saisies = 0

    # Nouvelles stats (Session 22)
    taux_admission = 0
    nb_admis = 0
    top_eleves = []

    # Config note de passage
    from core.models import ConfigurationEtablissement
    config, _ = ConfigurationEtablissement.objects.get_or_create(etablissement=etab)
    note_passage = float(config.note_passage) if config.note_passage else 10.0

    if annee_courante:
        classes_qs = Classe.objects.filter(
            etablissement=etab, annee_scolaire=annee_courante
        )
        nb_classes = classes_qs.count()

        inscriptions_qs = Inscription.objects.filter(
            classe__etablissement=etab,
            annee_scolaire=annee_courante,
            actif=True,
        )
        nb_eleves = inscriptions_qs.count()
        nb_garcons = inscriptions_qs.filter(eleve__sexe='M').count()
        nb_filles = inscriptions_qs.filter(eleve__sexe='F').count()

        nb_enseignants = Enseignant.objects.filter(etablissement=etab).count()

        # Moyenne établissement (basée sur moyenne_finale des notes)
        notes_qs = Note.objects.filter(
            trimestre__annee_scolaire=annee_courante.libelle,
            trimestre__etablissement=etab,
        )
        moyennes_finales = [
            n.moyenne_finale for n in notes_qs
            if n.moyenne_finale is not None
        ]
        if moyennes_finales:
            moyenne_generale = round(sum(moyennes_finales) / len(moyennes_finales), 2)

        # Effectif par classe (avec lien + tri)
        effectif_par_classe = list(
            classes_qs.annotate(
                nb=Count('inscriptions', filter=models.Q(inscriptions__actif=True))
            ).values('id', 'nom', 'niveau', 'nb').order_by('niveau', 'nom')
        )

        # Trimestre en cours
        trimestre_courant = Trimestre.objects.filter(
            etablissement=etab,
            annee_scolaire=annee_courante.libelle,
            cloture=False,
        ).order_by('numero').first()

        # Notes saisies (trimestre en cours)
        if trimestre_courant:
            nb_notes_saisies = Note.objects.filter(
                trimestre=trimestre_courant,
            ).count()

        # ===== Top 6 des meilleures moyennes (trimestre en cours) =====
        if trimestre_courant:
            # Pour chaque élève inscrit actif → moyenne du trimestre
            from decimal import Decimal
            matieres_classe_cache = {}

            eleves_data = []
            for insc in inscriptions_qs.select_related('eleve', 'classe'):
                eleve = insc.eleve
                classe = insc.classe
                if classe.id not in matieres_classe_cache:
                    matieres_classe_cache[classe.id] = list(
                        MatiereClasse.objects.filter(classe=classe)
                    )
                matieres_classe = matieres_classe_cache[classe.id]

                total = Decimal('0')
                coef_sum = Decimal('0')
                for mc in matieres_classe:
                    note = Note.objects.filter(
                        eleve=eleve, matiere=mc.matiere, trimestre=trimestre_courant
                    ).first()
                    if note and note.moyenne_finale is not None:
                        c = Decimal(str(mc.coefficient))
                        total += Decimal(str(note.moyenne_finale)) * c
                        coef_sum += c

                if coef_sum > 0:
                    moy = round(float(total / coef_sum), 2)
                    eleves_data.append({
                        'eleve': eleve,
                        'classe': classe,
                        'moyenne': moy,
                    })

            eleves_data.sort(key=lambda x: -x['moyenne'])
            top_eleves = eleves_data[:6]

        # ===== Taux d'admission (moyennes annuelles ≥ note de passage) =====
        # Calcul : pour chaque élève inscrit actif → moyenne annuelle
        # (moyenne des 3 trimestres)
        from decimal import Decimal as D
        trimestres_annee = list(
            Trimestre.objects.filter(
                etablissement=etab,
                annee_scolaire=annee_courante.libelle,
                numero__in=(1, 2, 3),
            ).order_by('numero')
        )

        if len(trimestres_annee) >= 1:
            nb_eleves_avec_moy = 0
            nb_eleves_admis = 0

            for insc in inscriptions_qs.select_related('eleve', 'classe'):
                eleve = insc.eleve
                classe = insc.classe
                if classe.id not in matieres_classe_cache:
                    matieres_classe_cache[classe.id] = list(
                        MatiereClasse.objects.filter(classe=classe)
                    )
                matieres_classe = matieres_classe_cache[classe.id]

                moyennes_trim = []
                for t in trimestres_annee:
                    tot = D('0')
                    cs = D('0')
                    for mc in matieres_classe:
                        note = Note.objects.filter(
                            eleve=eleve, matiere=mc.matiere, trimestre=t
                        ).first()
                        if note and note.moyenne_finale is not None:
                            c = D(str(mc.coefficient))
                            tot += D(str(note.moyenne_finale)) * c
                            cs += c
                    if cs > 0:
                        moyennes_trim.append(float(tot / cs))

                if len(moyennes_trim) == 3:
                    moy_annuelle = round(sum(moyennes_trim) / 3, 2)
                    nb_eleves_avec_moy += 1
                    if moy_annuelle >= note_passage:
                        nb_eleves_admis += 1

            if nb_eleves_avec_moy > 0:
                taux_admission = round((nb_eleves_admis / nb_eleves_avec_moy) * 100, 1)
                nb_admis = nb_eleves_admis

    context = {
        'titre': etab.nom,
        'etablissement': etab,
        'annee_courante': annee_courante,
        'annees_disponibles': annees_disponibles,
        'trimestre_courant': trimestre_courant,
        'nb_eleves': nb_eleves,
        'nb_garcons': nb_garcons,
        'nb_filles': nb_filles,
        'nb_classes': nb_classes,
        'nb_enseignants': nb_enseignants,
        'moyenne_generale': moyenne_generale,
        'effectif_par_classe': effectif_par_classe,
        'nb_notes_saisies': nb_notes_saisies,
        'taux_admission': taux_admission,
        'nb_admis': nb_admis,
        'note_passage': note_passage,
        'top_eleves': top_eleves,
    }
    return render(request, 'dashboard/chef_etablissement.html', context)


# =====================================================
# ENSEIGNANT
# =====================================================
@login_required
def enseignant_dashboard(request):
    """Tableau de bord pour l'enseignant : affiche ses classes/matières."""
    if request.user.profil.role != 'enseignant':
        return redirect('dashboard:redirection')

    etab = request.user.profil.etablissement
    if not etab:
        messages.error(request, "Aucun établissement lié à votre compte.")
        return redirect('accounts:logout')

    try:
        enseignant = request.user.enseignant
    except Exception:
        messages.error(request, "Votre profil enseignant est incomplet. Contactez le chef d'établissement.")
        return redirect('accounts:logout')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()

    trimestre_courant = None
    if annee:
        trimestre_courant = Trimestre.objects.filter(
            etablissement=etab,
            annee_scolaire=annee.libelle,
            cloture=False,
        ).order_by('numero').first()

    mes_affectations = []
    if annee:
        affectations_qs = MatiereClasse.objects.filter(
            enseignant=enseignant,
            classe__annee_scolaire=annee,
        ).select_related('classe', 'matiere').order_by('classe__niveau', 'classe__nom', 'matiere__ordre')

        for aff in affectations_qs:
            nb_eleves_inscrits = Inscription.objects.filter(
                classe=aff.classe, annee_scolaire=annee, actif=True
            ).count()

            nb_notes_saisies = 0
            if trimestre_courant:
                nb_notes_saisies = Note.objects.filter(
                    eleve__inscriptions__classe=aff.classe,
                    eleve__inscriptions__annee_scolaire=annee,
                    matiere=aff.matiere,
                    trimestre=trimestre_courant,
                ).distinct().count()

            if nb_notes_saisies == 0:
                statut = 'vide'
                statut_label = 'Aucune note'
                statut_color = 'secondary'
            elif nb_notes_saisies < nb_eleves_inscrits:
                statut = 'partiel'
                statut_label = f'{nb_notes_saisies}/{nb_eleves_inscrits}'
                statut_color = 'warning'
            else:
                statut = 'complet'
                statut_label = f'{nb_notes_saisies}/{nb_eleves_inscrits}'
                statut_color = 'success'

            mes_affectations.append({
                'affectation': aff,
                'nb_eleves': nb_eleves_inscrits,
                'nb_notes': nb_notes_saisies,
                'statut': statut,
                'statut_label': statut_label,
                'statut_color': statut_color,
            })

    context = {
        'titre': f'Bienvenue, {request.user.get_full_name() or request.user.username}',
        'etablissement': etab,
        'annee': annee,
        'trimestre_courant': trimestre_courant,
        'enseignant': enseignant,
        'mes_affectations': mes_affectations,
        'nb_affectations': len(mes_affectations),
    }
    return render(request, 'dashboard/enseignant.html', context)
