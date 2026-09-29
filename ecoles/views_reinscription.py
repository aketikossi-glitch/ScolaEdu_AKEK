"""
ScolaEdu_AKEK — Réinscription automatique en classe supérieure.
Session 21 (v3) :
  - Sélection manuelle année source + année cible
  - Preview INTERACTIF : chaque élève a un <select> pour choisir sa classe cible
  - Boutons globaux « Placer tous les [niveau] en [classe] »
  - Redoublants : pré-sélection même classe si existe
  - Passants : choix obligatoire si plusieurs classes du niveau cible
  - Exécution avec backup + rapport
"""
import os
import shutil
from datetime import date, datetime
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings

from core.models import (
    AnneeScolaire, Trimestre, Classe, Inscription, Eleve,
    MatiereClasse, Note, ConfigurationEtablissement,
)
from .views import _get_etablissement_chef


# =====================================================
# MAPPING DES NIVEAUX
# =====================================================
MAP_PASSAGE = {
    'maternelle': 'cp1',
    'cp1': 'cp2',
    'cp2': 'ce1',
    'ce1': 'ce2',
    'ce2': 'cm1',
    'cm1': 'cm2',
    '6eme': '5eme',
    '5eme': '4eme',
    '4eme': '3eme',
    '2nde': '1ere',
}
NIVEAUX_EXAMEN = {'cm2', '3eme', '1ere', 'tle'}


# =====================================================
# HELPERS
# =====================================================
def _moyenne_annuelle_eleve(eleve, classe, annee_libelle):
    """Calcule la moyenne annuelle = moyenne des moyennes trimestrielles."""
    trimestres = Trimestre.objects.filter(
        etablissement=classe.etablissement,
        annee_scolaire=annee_libelle,
        numero__in=(1, 2, 3),
    ).order_by('numero')

    matieres_classe = MatiereClasse.objects.filter(classe=classe)
    moyennes_trimestres = []
    details_trimestres = []

    for t in trimestres:
        total = Decimal('0')
        coef_sum = Decimal('0')
        for mc in matieres_classe:
            note = Note.objects.filter(
                eleve=eleve, matiere=mc.matiere, trimestre=t
            ).first()
            if note and note.moyenne_finale is not None:
                c = Decimal(str(mc.coefficient))
                total += Decimal(str(note.moyenne_finale)) * c
                coef_sum += c
        if coef_sum > 0:
            moy = round(float(total / coef_sum), 2)
            moyennes_trimestres.append(moy)
            details_trimestres.append({'numero': t.numero, 'moyenne': moy})
        else:
            details_trimestres.append({'numero': t.numero, 'moyenne': None})

    moy_annuelle = None
    if len(moyennes_trimestres) == 3:
        moy_annuelle = round(sum(moyennes_trimestres) / 3, 2)

    return moy_annuelle, details_trimestres


def _determiner_decision(eleve, classe, moy_annuelle, note_passage):
    """Retourne la décision pour un élève."""
    niveau = classe.niveau

    if niveau in NIVEAUX_EXAMEN:
        return {
            'decision': 'examen',
            'niveau_cible': None,
            'raison': "Classe d'examen — sortie du cycle",
        }

    niveau_cible = MAP_PASSAGE.get(niveau)
    if not niveau_cible:
        return {
            'decision': 'examen',
            'niveau_cible': None,
            'raison': "Niveau non géré automatiquement",
        }

    if moy_annuelle is not None and moy_annuelle >= note_passage:
        return {
            'decision': 'passe',
            'niveau_cible': niveau_cible,
            'raison': f"Moyenne {moy_annuelle} ≥ {note_passage}",
        }

    if moy_annuelle is None:
        raison = "Moyenne annuelle indisponible (notes incomplètes)"
    else:
        raison = f"Moyenne {moy_annuelle} < {note_passage}"

    return {
        'decision': 'redouble',
        'niveau_cible': niveau,
        'raison': raison,
    }


def _pre_selection_classe(classe_src, niveau_cible, classes_disponibles):
    """
    Détermine la classe pré-sélectionnée pour un élève.
    - Si aucune classe dispo → None
    - Si 1 seule classe → celle-là
    - Si plusieurs :
        * Chercher un nom identique au nom source (ex: "6ème A" → "6ème A")
        * Sinon, chercher partiel ("6ème A" dans "6ème A") 
        * Sinon, retourner None (l'utilisateur DOIT choisir)
    """
    if not classes_disponibles:
        return None
    if len(classes_disponibles) == 1:
        return classes_disponibles[0]

    # Tentative de matching par nom exact
    nom_src = classe_src.nom
    for c in classes_disponibles:
        if c.nom.lower() == nom_src.lower():
            return c
    # Matching partiel (basé sur la dernière lettre ou chiffre)
    for c in classes_disponibles:
        if nom_src.lower() in c.nom.lower() or c.nom.lower() in nom_src.lower():
            return c

    return None


# =====================================================
# VUE 1 — PRÉVISUALISATION
# =====================================================
@login_required
def reinscription_preview(request):
    """Page de sélection des années + preview interactif."""
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')

    toutes_annees = AnneeScolaire.objects.filter(etablissement=etab).order_by('-libelle')
    if not toutes_annees.exists():
        messages.warning(request, "Aucune année scolaire. Créez-en une d'abord.")
        return redirect('ecoles:annee_creer')

    annee_src_id = request.GET.get('annee_src')
    annee_cible_id = request.GET.get('annee_cible')

    annee_src = toutes_annees.filter(id=annee_src_id).first() if annee_src_id else None
    annee_cible = toutes_annees.filter(id=annee_cible_id).first() if annee_cible_id else None

    config, _ = ConfigurationEtablissement.objects.get_or_create(etablissement=etab)
    note_passage = float(config.note_passage) if config.note_passage else 10.0

    # Écran de sélection
    if not annee_src or not annee_cible:
        annee_src_defaut = toutes_annees.filter(en_cours=True).first() or toutes_annees.first()
        annee_cible_defaut = toutes_annees.exclude(id=annee_src_defaut.id).order_by('-libelle').first()

        context = {
            'etablissement': etab,
            'toutes_annees': toutes_annees,
            'annee_src': annee_src_defaut,
            'annee_cible': annee_cible_defaut,
            'note_passage': note_passage,
            'etape': 'selection',
        }
        return render(request, 'ecoles/reinscription/preview.html', context)

    if annee_src.id == annee_cible.id:
        messages.error(request, "L'année source et l'année cible doivent être différentes.")
        return redirect('ecoles:reinscription_preview')

    # ===== Récupérer TOUTES les classes de l'année cible =====
    classes_cible_qs = Classe.objects.filter(
        etablissement=etab, annee_scolaire=annee_cible
    ).order_by('niveau', 'nom')

    # Dictionnaire niveau → liste de classes cibles
    classes_par_niveau = {}
    for c in classes_cible_qs:
        classes_par_niveau.setdefault(c.niveau, []).append(c)

    # ===== Calcul du preview =====
    inscriptions = Inscription.objects.filter(
        annee_scolaire=annee_src, actif=True,
        classe__etablissement=etab,
    ).select_related('eleve', 'classe').order_by(
        'classe__niveau', 'classe__nom', 'eleve__nom', 'eleve__prenom'
    )

    lignes = []
    compteurs = {'passe': 0, 'redouble': 0, 'examen': 0, 'erreur': 0}

    for insc in inscriptions:
        eleve = insc.eleve
        classe = insc.classe

        moy_annuelle, details = _moyenne_annuelle_eleve(eleve, classe, annee_src.libelle)
        decision = _determiner_decision(eleve, classe, moy_annuelle, note_passage)

        classes_dispo = []
        classe_pre_selection = None
        erreur_cible = None

        if decision['decision'] in ('passe', 'redouble'):
            classes_dispo = classes_par_niveau.get(decision['niveau_cible'], [])
            if not classes_dispo:
                erreur_cible = f"Aucune classe de niveau '{decision['niveau_cible']}' dans {annee_cible.libelle}"
            else:
                classe_pre_selection = _pre_selection_classe(
                    classe, decision['niveau_cible'], classes_dispo
                )

        if erreur_cible:
            compteurs['erreur'] += 1
        else:
            compteurs[decision['decision']] += 1

        lignes.append({
            'eleve': eleve,
            'classe_src': classe,
            'moy_annuelle': moy_annuelle,
            'details_trimestres': details,
            'decision': decision['decision'],
            'raison': decision['raison'],
            'niveau_cible': decision['niveau_cible'],
            'classes_dispo': classes_dispo,
            'classe_pre_selection': classe_pre_selection,
            'erreur_cible': erreur_cible,
        })

    # Groupement par niveau cible (pour les boutons globaux)
    # → dict : niveau_cible → {libelle_niveau, classes_dispo}
    groupes_niveaux = {}
    for l in lignes:
        if l['decision'] in ('passe', 'redouble') and l['niveau_cible']:
            nc = l['niveau_cible']
            if nc not in groupes_niveaux:
                # Nombre d'élèves de ce niveau cible
                nb = sum(1 for x in lignes if x['niveau_cible'] == nc and x['decision'] in ('passe', 'redouble'))
                classes = classes_par_niveau.get(nc, [])
                # Libellé du niveau (à partir de la 1ère classe ou fallback)
                libelle = nc
                if classes:
                    libelle = classes[0].get_niveau_display()
                groupes_niveaux[nc] = {
                    'niveau': nc,
                    'libelle': libelle,
                    'nb_eleves': nb,
                    'classes': classes,
                }

    context = {
        'etablissement': etab,
        'toutes_annees': toutes_annees,
        'annee_src': annee_src,
        'annee_cible': annee_cible,
        'note_passage': note_passage,
        'lignes': lignes,
        'compteurs': compteurs,
        'total': len(lignes),
        'groupes_niveaux': groupes_niveaux.values(),
        'etape': 'preview',
    }
    return render(request, 'ecoles/reinscription/preview.html', context)


# =====================================================
# VUE 2 — EXÉCUTION
# =====================================================
@login_required
def reinscription_executer(request):
    """Exécute la réinscription avec les choix de classes du formulaire."""
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')

    if request.method != 'POST':
        return redirect('ecoles:reinscription_preview')

    confirmation = request.POST.get('confirmation', '').strip()
    if confirmation != 'CONFIRMER':
        messages.error(request, "Saisissez exactement « CONFIRMER » pour valider.")
        return redirect('ecoles:reinscription_preview')

    annee_src_id = request.POST.get('annee_src')
    annee_cible_id = request.POST.get('annee_cible')

    annee_src = get_object_or_404(AnneeScolaire, id=annee_src_id, etablissement=etab)
    annee_cible = get_object_or_404(AnneeScolaire, id=annee_cible_id, etablissement=etab)

    if annee_src.id == annee_cible.id:
        messages.error(request, "Année source et cible identiques.")
        return redirect('ecoles:reinscription_preview')

    # ===== Backup automatique =====
    db_path = settings.DATABASES['default']['NAME']
    backup_dir = os.path.dirname(db_path)
    backup_name = f"db.sqlite3.backup_reinscription_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_path = os.path.join(backup_dir, backup_name)
    try:
        shutil.copy2(db_path, backup_path)
        backup_ok = backup_name
    except Exception as e:
        backup_ok = None
        messages.warning(request, f"⚠️ Backup échoué : {e}. Opération annulée.")
        return redirect('ecoles:reinscription_preview')

    config, _ = ConfigurationEtablissement.objects.get_or_create(etablissement=etab)
    note_passage = float(config.note_passage) if config.note_passage else 10.0

    # ===== Récupérer les classes cibles valides =====
    classes_cible_ids = set(
        Classe.objects.filter(etablissement=etab, annee_scolaire=annee_cible)
        .values_list('id', flat=True)
    )

    inscriptions = Inscription.objects.filter(
        annee_scolaire=annee_src, actif=True,
        classe__etablissement=etab,
    ).select_related('eleve', 'classe')

    rapport = {
        'passes': 0,
        'redoublants': 0,
        'exclus': 0,
        'erreurs': [],
        'ignores': 0,
        'backup': backup_ok,
    }

    for insc in inscriptions:
        eleve = insc.eleve
        classe_src = insc.classe

        moy_annuelle, _ = _moyenne_annuelle_eleve(eleve, classe_src, annee_src.libelle)
        decision = _determiner_decision(eleve, classe_src, moy_annuelle, note_passage)

        # Classe d'examen → ignorée
        if decision['decision'] == 'examen':
            rapport['exclus'] += 1
            continue

        # Récupérer le choix de classe cible depuis le POST
        classe_cible_id = request.POST.get(f'classe_cible_{eleve.id}')

        if not classe_cible_id:
            rapport['erreurs'].append(
                f"{eleve.nom_complet} : aucune classe cible n'a été choisie"
            )
            continue

        try:
            classe_cible_id_int = int(classe_cible_id)
        except (ValueError, TypeError):
            rapport['erreurs'].append(f"{eleve.nom_complet} : classe cible invalide")
            continue

        # Vérifier que la classe appartient bien à l'année cible + à l'étab
        if classe_cible_id_int not in classes_cible_ids:
            rapport['erreurs'].append(
                f"{eleve.nom_complet} : classe cible introuvable ou invalide"
            )
            continue

        classe_cible = Classe.objects.get(id=classe_cible_id_int)

        # Vérifier si déjà inscrit dans l'année cible
        existant = Inscription.objects.filter(
            eleve=eleve, annee_scolaire=annee_cible
        ).first()

        if existant:
            rapport['ignores'] += 1
            continue

        # Créer l'inscription
        try:
            Inscription.objects.create(
                eleve=eleve,
                classe=classe_cible,
                annee_scolaire=annee_cible,
                actif=True,
            )

            if decision['decision'] == 'passe':
                eleve.statut = 'nouveau'
                rapport['passes'] += 1
            else:
                eleve.statut = 'redoublant'
                rapport['redoublants'] += 1
            eleve.save(update_fields=['statut'])

        except Exception as e:
            rapport['erreurs'].append(f"{eleve.nom_complet} : {e}")

    messages.success(
        request,
        f"✅ Réinscription terminée : {rapport['passes']} passage(s), "
        f"{rapport['redoublants']} redoublant(s), "
        f"{rapport['exclus']} exclu(s), "
        f"{rapport['ignores']} ignoré(s), "
        f"{len(rapport['erreurs'])} erreur(s). "
        f"Backup : {rapport['backup']}"
    )

    context = {
        'etablissement': etab,
        'annee_src': annee_src,
        'annee_cible': annee_cible,
        'rapport': rapport,
    }
    return render(request, 'ecoles/reinscription/resultat.html', context)
