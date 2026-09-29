from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Max, Count, Q
from datetime import timedelta
from decimal import Decimal
from core.models import (
    AnneeScolaire, Trimestre, Classe, Inscription, MatiereClasse,
    Note, Matiere, Enseignant, Eleve
)
from .forms import (
    AnneeScolaireForm, TrimestresForm,
    ConfigurationEtablissementForm, ClasseForm, MatiereForm,
    MatiereClasseForm, AffectationEnMasseForm,
    EleveForm, InscriptionForm
)


# =====================================================
# HELPERS
# =====================================================
def _get_etablissement_chef(request):
    """Retourne l'établissement du chef/secrétaire connecté."""
    if request.user.profil.role not in ('chef_etablissement', 'secretaire'):
        return None
    return request.user.profil.etablissement


def _get_etablissement_user(request):
    """Retourne l'établissement de N'IMPORTE QUEL utilisateur."""
    try:
        return request.user.profil.etablissement
    except Exception:
        return None


def _get_enseignant_user(request):
    """Retourne l'objet Enseignant si l'utilisateur connecté en est un, sinon None."""
    try:
        if request.user.profil.role == 'enseignant':
            return request.user.enseignant
    except Exception:
        pass
    return None


def _get_classes_autorisees(request):
    """
    Retourne le queryset des classes que l'utilisateur peut gérer.
    - Chef/secrétaire : TOUTES les classes de l'établissement
    - Enseignant : UNIQUEMENT les classes où il enseigne
    """
    etab = _get_etablissement_user(request)
    if not etab:
        return Classe.objects.none()

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        return Classe.objects.none()

    enseignant = _get_enseignant_user(request)
    if enseignant:
        classes_ids = MatiereClasse.objects.filter(
            enseignant=enseignant,
            classe__annee_scolaire=annee
        ).values_list('classe_id', flat=True).distinct()
        return Classe.objects.filter(id__in=classes_ids).order_by('niveau', 'nom')

    return Classe.objects.filter(etablissement=etab, annee_scolaire=annee).order_by('niveau', 'nom')


def _get_matieres_autorisees(request, classe=None):
    """
    Retourne les matières autorisées.
    - Chef/secrétaire : toutes les matières
    - Enseignant : uniquement ses matières (filtrées par classe si passée)
    """
    etab = _get_etablissement_user(request)
    if not etab:
        return Matiere.objects.none()

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        return Matiere.objects.none()

    enseignant = _get_enseignant_user(request)
    if enseignant:
        qs = MatiereClasse.objects.filter(enseignant=enseignant, classe__annee_scolaire=annee)
        if classe:
            qs = qs.filter(classe=classe)
        matieres_ids = qs.values_list('matiere_id', flat=True).distinct()
        return Matiere.objects.filter(id__in=matieres_ids).order_by('ordre', 'nom')

    return Matiere.objects.filter(etablissement=etab, annee_scolaire=annee).order_by('ordre', 'nom')


def _verifier_acces_classe(request, classe):
    """Lève une erreur si l'utilisateur n'a pas accès à cette classe."""
    classes_autorisees = _get_classes_autorisees(request)
    if not classes_autorisees.filter(id=classe.id).exists():
        return False
    return True


def _verifier_acces_matiere_classe(request, classe, matiere):
    """Vérifie que l'utilisateur peut saisir des notes pour cette classe + matière."""
    enseignant = _get_enseignant_user(request)
    if enseignant:
        return MatiereClasse.objects.filter(
            classe=classe, matiere=matiere, enseignant=enseignant
        ).exists()
    return MatiereClasse.objects.filter(classe=classe, matiere=matiere).exists()


def _add_months(source_date, months):
    mois = source_date.month - 1 + months
    annee = source_date.year + mois // 12
    mois = mois % 12 + 1
    from calendar import monthrange
    jour = min(source_date.day, monthrange(annee, mois)[1])
    from datetime import date
    return date(annee, mois, jour)


def _classe_contient_donnees(classe):
    nb_inscriptions = Inscription.objects.filter(classe=classe).count()
    if nb_inscriptions > 0:
        return True, f"{nb_inscriptions} inscription(s)"
    nb_matieres = MatiereClasse.objects.filter(classe=classe).count()
    if nb_matieres > 0:
        return True, f"{nb_matieres} matière(s) affectée(s)"
    return False, ""


def _matiere_contient_donnees(matiere):
    nb_classes = MatiereClasse.objects.filter(matiere=matiere).count()
    if nb_classes > 0:
        return True, f"{nb_classes} classe(s) affectée(s)"
    nb_notes = Note.objects.filter(matiere=matiere).count()
    if nb_notes > 0:
        return True, f"{nb_notes} note(s) saisie(s)"
    return False, ""


def _calculer_ordre_suivant(etab, annee):
    dernier = Matiere.objects.filter(etablissement=etab, annee_scolaire=annee).aggregate(Max('ordre'))['ordre__max']
    return (dernier or 0) + 1


def _generer_matricule(etablissement, annee_libelle):
    prefixe = annee_libelle[:4] if annee_libelle else 'AAAA'
    derniers = Eleve.objects.filter(
        etablissement=etablissement,
        matricule__startswith=f"{prefixe}-"
    ).order_by('-matricule')
    if derniers.exists():
        dernier = derniers.first().matricule
        try:
            numero = int(dernier.split('-')[1]) + 1
        except (IndexError, ValueError):
            numero = 1
    else:
        numero = 1
    return f"{prefixe}-{numero:04d}"


# =====================================================
# ANNÉES
# =====================================================
@login_required
def annee_liste(request):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    annees = AnneeScolaire.objects.filter(etablissement=etab).order_by('-libelle')
    return render(request, 'ecoles/annee_liste.html', {'etablissement': etab, 'annees': annees})


@login_required
def annee_creer(request):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')

    if request.method == 'POST':
        form = AnneeScolaireForm(request.POST)
        if form.is_valid():
            annee = form.save(commit=False)
            annee.etablissement = etab
            if AnneeScolaire.objects.filter(etablissement=etab, libelle=annee.libelle).exists():
                messages.error(request, f"L'année '{annee.libelle}' existe déjà.")
            else:
                ancienne = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
                annee.save()
                if ancienne and annee.en_cours:
                    messages.warning(request, f"⚠️ '{ancienne.libelle}' clôturée. '{annee.libelle}' active.")
                else:
                    messages.success(request, f"✅ Année '{annee.libelle}' créée !")
                return redirect('dashboard:chef_etablissement')
    else:
        from datetime import date
        a = date.today().year
        form = AnneeScolaireForm(initial={
            'libelle': f"{a}-{a+1}",
            'date_debut': date(a, 10, 1),
            'date_fin': date(a+1, 6, 30),
            'en_cours': True,
        })

    return render(request, 'ecoles/annee_form.html', {'form': form, 'etablissement': etab, 'titre': 'Nouvelle année scolaire'})


@login_required
def annee_activer(request, annee_id):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    annee = get_object_or_404(AnneeScolaire, id=annee_id, etablissement=etab)
    annee.en_cours = True
    annee.save()
    messages.success(request, f"Année '{annee.libelle}' activée.")
    return redirect('dashboard:chef_etablissement')


@login_required
def annee_rouvrir(request, annee_id):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    annee = get_object_or_404(AnneeScolaire, id=annee_id, etablissement=etab)
    if annee.en_cours:
        return redirect('dashboard:chef_etablissement')

    ancienne = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    annee.en_cours = True
    annee.save()
    if ancienne:
        messages.warning(request, f"⚠️ '{ancienne.libelle}' clôturée. '{annee.libelle}' active.")
    else:
        messages.success(request, f"✅ Année '{annee.libelle}' rouverte.")
    return redirect('dashboard:chef_etablissement')


# =====================================================
# TRIMESTRES
# =====================================================
@login_required
def trimestre_liste(request):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.warning(request, "Créez d'abord une année scolaire.")
        return redirect('ecoles:annee_creer')
    trimestres = Trimestre.objects.filter(etablissement=etab, annee_scolaire=annee.libelle).order_by('numero')
    return render(request, 'ecoles/trimestre_liste.html', {'etablissement': etab, 'annee': annee, 'trimestres': trimestres})


@login_required
def trimestre_generer(request):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.warning(request, "Créez d'abord une année scolaire.")
        return redirect('ecoles:annee_creer')

    if request.method == 'POST':
        Trimestre.objects.filter(etablissement=etab, annee_scolaire=annee.libelle).delete()
        form = TrimestresForm(request.POST)
        if form.is_valid():
            d1 = int(form.cleaned_data['duree_trimestre1'])
            d2 = int(form.cleaned_data['duree_trimestre2'])
            d3 = int(form.cleaned_data['duree_trimestre3'])
            pause = int(form.cleaned_data['pause_jours'])

            debut = annee.date_debut
            t1_debut = debut
            t1_fin = _add_months(t1_debut, d1) - timedelta(days=1)
            t2_debut = t1_fin + timedelta(days=pause + 1)
            t2_fin = _add_months(t2_debut, d2) - timedelta(days=1)
            t3_debut = t2_fin + timedelta(days=pause + 1)
            t3_fin = annee.date_fin

            for numero, d_debut, d_fin in [(1, t1_debut, t1_fin), (2, t2_debut, t2_fin), (3, t3_debut, t3_fin)]:
                Trimestre.objects.create(etablissement=etab, numero=numero, annee_scolaire=annee.libelle, date_debut=d_debut, date_fin=d_fin, cloture=False)

            messages.success(request, f"✅ 3 trimestres de {annee.libelle} créés !")
            return redirect('dashboard:chef_etablissement')
    else:
        form = TrimestresForm()

    return render(request, 'ecoles/trimestre_form.html', {'form': form, 'etablissement': etab, 'annee': annee, 'titre': f'Créer les trimestres — {annee.libelle}'})


@login_required
def trimestre_cloturer(request, trimestre_id):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    trimestre = get_object_or_404(Trimestre, id=trimestre_id, etablissement=etab)
    trimestre.cloture = True
    trimestre.save()
    messages.success(request, f"{trimestre.get_numero_display()} clôturé.")
    return redirect('ecoles:trimestre_liste')


# =====================================================
# CONFIGURATION
# =====================================================
@login_required
def configuration_etablissement(request):
    from core.models import ConfigurationEtablissement

    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')

    config, created = ConfigurationEtablissement.objects.get_or_create(etablissement=etab)

    if request.method == 'POST':
        form = ConfigurationEtablissementForm(request.POST, request.FILES, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Configuration enregistrée !")
            return redirect('ecoles:configuration')
    else:
        form = ConfigurationEtablissementForm(instance=config)

    return render(request, 'ecoles/configuration.html', {'form': form, 'etablissement': etab, 'config': config, 'titre': 'Configuration'})


# =====================================================
# CLASSES
# =====================================================
@login_required
def classe_liste(request):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.warning(request, "Créez d'abord une année scolaire.")
        return redirect('ecoles:annee_creer')

    classes_qs = Classe.objects.filter(etablissement=etab, annee_scolaire=annee).order_by('niveau', 'nom')

    classes_par_niveau = {}
    for classe in classes_qs:
        niveau_display = classe.get_niveau_display()
        if niveau_display not in classes_par_niveau:
            classes_par_niveau[niveau_display] = []
        classe.nb_inscrits = Inscription.objects.filter(classe=classe, actif=True).count()
        classe.nb_matieres = MatiereClasse.objects.filter(classe=classe).count()
        contient, raison = _classe_contient_donnees(classe)
        classe.peut_supprimer = not contient
        classe.raison_blocage = raison
        classes_par_niveau[niveau_display].append(classe)

    return render(request, 'ecoles/classe_liste.html', {
        'etablissement': etab, 'annee': annee,
        'classes_par_niveau': classes_par_niveau,
        'total_classes': classes_qs.count(),
    })


@login_required
def classe_creer(request):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.warning(request, "Créez d'abord une année scolaire.")
        return redirect('ecoles:annee_creer')

    if request.method == 'POST':
        form = ClasseForm(request.POST, etablissement=etab, annee_scolaire=annee)
        if form.is_valid():
            classe = form.save(commit=False)
            classe.etablissement = etab
            classe.annee_scolaire = annee
            classe.save()
            messages.success(request, f"✅ Classe '{classe.nom}' créée !")
            return redirect('ecoles:classe_liste')
    else:
        form = ClasseForm(etablissement=etab, annee_scolaire=annee)

    return render(request, 'ecoles/classe_form.html', {'form': form, 'etablissement': etab, 'annee': annee, 'titre': 'Nouvelle classe', 'mode': 'creer'})


@login_required
def classe_modifier(request, classe_id):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    classe = get_object_or_404(Classe, id=classe_id, etablissement=etab)
    annee = classe.annee_scolaire

    if request.method == 'POST':
        form = ClasseForm(request.POST, instance=classe, etablissement=etab, annee_scolaire=annee)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Classe '{classe.nom}' modifiée !")
            return redirect('ecoles:classe_liste')
    else:
        form = ClasseForm(instance=classe, etablissement=etab, annee_scolaire=annee)

    return render(request, 'ecoles/classe_form.html', {'form': form, 'etablissement': etab, 'annee': annee, 'classe': classe, 'titre': f'Modifier — {classe.nom}', 'mode': 'modifier'})


@login_required
def classe_supprimer(request, classe_id):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    classe = get_object_or_404(Classe, id=classe_id, etablissement=etab)

    contient, raison = _classe_contient_donnees(classe)
    if contient:
        messages.error(request, f"❌ Impossible de supprimer '{classe.nom}' : {raison}.")
        return redirect('ecoles:classe_liste')

    if request.method == 'POST':
        nom = classe.nom
        classe.delete()
        messages.success(request, f"🗑️ Classe '{nom}' supprimée.")
        return redirect('ecoles:classe_liste')

    return render(request, 'ecoles/classe_supprimer.html', {'classe': classe, 'etablissement': etab, 'titre': f'Supprimer — {classe.nom}'})


@login_required
def classe_titulaire(request, classe_id):
    """Vue dédiée pour affecter rapidement un titulaire à une classe."""
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')

    classe = get_object_or_404(Classe, id=classe_id, etablissement=etab)
    enseignants = Enseignant.objects.filter(etablissement=etab).order_by('user__last_name', 'user__first_name')

    if request.method == 'POST':
        titulaire_id = request.POST.get('titulaire') or None
        if titulaire_id:
            try:
                titulaire = Enseignant.objects.get(id=titulaire_id, etablissement=etab)
                classe.titulaire = titulaire
            except Enseignant.DoesNotExist:
                messages.error(request, "Enseignant introuvable.")
                return redirect('ecoles:classe_titulaire', classe_id=classe.id)
        else:
            classe.titulaire = None

        classe.save()
        messages.success(request, f"✅ Titulaire de {classe.nom} mis à jour.")
        return redirect('ecoles:classe_liste')

    return render(request, 'ecoles/classe_titulaire.html', {
        'etablissement': etab,
        'classe': classe,
        'enseignants': enseignants,
        'titre': f"Titulaire — {classe.nom}",
    })


# =====================================================
# MATIÈRES
# =====================================================
@login_required
def matiere_liste(request):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.warning(request, "Créez d'abord une année scolaire.")
        return redirect('ecoles:annee_creer')

    matieres = list(Matiere.objects.filter(etablissement=etab, annee_scolaire=annee).order_by('ordre', 'nom'))
    for matiere in matieres:
        matiere.nb_classes = MatiereClasse.objects.filter(matiere=matiere).count()
        matiere.nb_notes = Note.objects.filter(matiere=matiere).count()
        contient, raison = _matiere_contient_donnees(matiere)
        matiere.peut_supprimer = not contient
        matiere.raison_blocage = raison

    return render(request, 'ecoles/matiere_liste.html', {'etablissement': etab, 'annee': annee, 'matieres': matieres, 'total': len(matieres)})


@login_required
def matiere_creer(request):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.warning(request, "Créez d'abord une année scolaire.")
        return redirect('ecoles:annee_creer')

    if request.method == 'POST':
        form = MatiereForm(request.POST, etablissement=etab, annee_scolaire=annee)
        if form.is_valid():
            matiere = form.save(commit=False)
            matiere.etablissement = etab
            matiere.annee_scolaire = annee
            matiere.save()
            messages.success(request, f"✅ Matière '{matiere.nom}' créée !")
            return redirect('ecoles:matiere_liste')
    else:
        form = MatiereForm(etablissement=etab, annee_scolaire=annee, initial={'ordre': _calculer_ordre_suivant(etab, annee), 'coefficient': 1})

    return render(request, 'ecoles/matiere_form.html', {'form': form, 'etablissement': etab, 'annee': annee, 'titre': 'Nouvelle matière', 'mode': 'creer'})


@login_required
def matiere_modifier(request, matiere_id):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    matiere = get_object_or_404(Matiere, id=matiere_id, etablissement=etab)
    annee = matiere.annee_scolaire

    if request.method == 'POST':
        form = MatiereForm(request.POST, instance=matiere, etablissement=etab, annee_scolaire=annee)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Matière '{matiere.nom}' modifiée !")
            return redirect('ecoles:matiere_liste')
    else:
        form = MatiereForm(instance=matiere, etablissement=etab, annee_scolaire=annee)

    return render(request, 'ecoles/matiere_form.html', {'form': form, 'etablissement': etab, 'annee': annee, 'matiere': matiere, 'titre': f'Modifier — {matiere.nom}', 'mode': 'modifier'})


@login_required
def matiere_supprimer(request, matiere_id):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    matiere = get_object_or_404(Matiere, id=matiere_id, etablissement=etab)

    contient, raison = _matiere_contient_donnees(matiere)
    if contient:
        messages.error(request, f"❌ Impossible de supprimer '{matiere.nom}' : {raison}.")
        return redirect('ecoles:matiere_liste')

    if request.method == 'POST':
        nom = matiere.nom
        matiere.delete()
        messages.success(request, f"🗑️ Matière '{nom}' supprimée.")
        return redirect('ecoles:matiere_liste')

    return render(request, 'ecoles/matiere_supprimer.html', {'matiere': matiere, 'etablissement': etab, 'titre': f'Supprimer — {matiere.nom}'})


# =====================================================
# MATIÈRES PAR CLASSE
# =====================================================
@login_required
def matiereclasse_choisir(request):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.warning(request, "Créez d'abord une année scolaire.")
        return redirect('ecoles:annee_creer')

    classes = Classe.objects.filter(etablissement=etab, annee_scolaire=annee).order_by('niveau', 'nom')
    for classe in classes:
        classe.nb_matieres_affectees = MatiereClasse.objects.filter(classe=classe).count()

    return render(request, 'ecoles/matiereclasse_choisir.html', {
        'etablissement': etab, 'annee': annee, 'classes': classes,
        'total_matieres': Matiere.objects.filter(etablissement=etab, annee_scolaire=annee).count(),
    })


@login_required
def matiereclasse_liste(request, classe_id):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    classe = get_object_or_404(Classe, id=classe_id, etablissement=etab)

    affectations = MatiereClasse.objects.filter(classe=classe).select_related('matiere', 'enseignant__user').order_by('matiere__ordre', 'matiere__nom')
    for aff in affectations:
        aff.nb_notes = Note.objects.filter(matiere=aff.matiere, eleve__inscriptions__classe=classe).distinct().count()
        aff.peut_supprimer = (aff.nb_notes == 0)

    return render(request, 'ecoles/matiereclasse_liste.html', {
        'etablissement': etab, 'annee': classe.annee_scolaire,
        'classe': classe, 'affectations': affectations, 'total': affectations.count(),
    })


@login_required
def matiereclasse_affecter(request, classe_id):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    classe = get_object_or_404(Classe, id=classe_id, etablissement=etab)

    if request.method == 'POST':
        form = MatiereClasseForm(request.POST, classe=classe, etablissement=etab)
        if form.is_valid():
            affectation = form.save(commit=False)
            affectation.classe = classe
            affectation.save()
            messages.success(request, f"✅ '{affectation.matiere.nom}' affectée à {classe.nom}.")
            return redirect('ecoles:matiereclasse_liste', classe_id=classe.id)
    else:
        form = MatiereClasseForm(classe=classe, etablissement=etab)

    return render(request, 'ecoles/matiereclasse_form.html', {
        'form': form, 'etablissement': etab, 'annee': classe.annee_scolaire,
        'classe': classe, 'titre': f'Affecter une matière — {classe.nom}', 'mode': 'creer',
    })


@login_required
def matiereclasse_affecter_masse(request, classe_id):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    classe = get_object_or_404(Classe, id=classe_id, etablissement=etab)

    if request.method == 'POST':
        form = AffectationEnMasseForm(request.POST, classe=classe, etablissement=etab)
        if form.is_valid():
            matieres = form.cleaned_data['matieres']
            count = 0
            for matiere in matieres:
                MatiereClasse.objects.create(classe=classe, matiere=matiere, coefficient=matiere.coefficient)
                count += 1
            messages.success(request, f"✅ {count} matière(s) affectée(s) à {classe.nom} !")
            return redirect('ecoles:matiereclasse_liste', classe_id=classe.id)
    else:
        form = AffectationEnMasseForm(classe=classe, etablissement=etab)

    return render(request, 'ecoles/matiereclasse_masse.html', {
        'form': form, 'etablissement': etab, 'annee': classe.annee_scolaire,
        'classe': classe, 'titre': f'Affecter en masse — {classe.nom}',
    })


@login_required
def matiereclasse_modifier(request, affectation_id):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    affectation = get_object_or_404(MatiereClasse, id=affectation_id, classe__etablissement=etab)
    classe = affectation.classe

    if request.method == 'POST':
        form = MatiereClasseForm(request.POST, instance=affectation, classe=classe, etablissement=etab)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Affectation modifiée.")
            return redirect('ecoles:matiereclasse_liste', classe_id=classe.id)
    else:
        form = MatiereClasseForm(instance=affectation, classe=classe, etablissement=etab)

    return render(request, 'ecoles/matiereclasse_form.html', {
        'form': form, 'etablissement': etab, 'annee': classe.annee_scolaire,
        'classe': classe, 'affectation': affectation,
        'titre': f'Modifier — {affectation.matiere.nom}', 'mode': 'modifier',
    })


@login_required
def matiereclasse_supprimer(request, affectation_id):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    affectation = get_object_or_404(MatiereClasse, id=affectation_id, classe__etablissement=etab)
    classe = affectation.classe

    nb_notes = Note.objects.filter(matiere=affectation.matiere, eleve__inscriptions__classe=classe).distinct().count()
    if nb_notes > 0:
        messages.error(request, f"❌ Impossible de retirer '{affectation.matiere.nom}' : {nb_notes} note(s).")
        return redirect('ecoles:matiereclasse_liste', classe_id=classe.id)

    if request.method == 'POST':
        nom = affectation.matiere.nom
        affectation.delete()
        messages.success(request, f"🗑️ '{nom}' retirée de {classe.nom}.")
        return redirect('ecoles:matiereclasse_liste', classe_id=classe.id)

    return render(request, 'ecoles/matiereclasse_supprimer.html', {
        'affectation': affectation, 'classe': classe, 'etablissement': etab,
        'titre': f'Retirer — {affectation.matiere.nom}',
    })


# =====================================================
# ÉLÈVES
# =====================================================
@login_required
def eleve_liste(request):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.warning(request, "Créez d'abord une année scolaire.")
        return redirect('ecoles:annee_creer')

    classe_id = request.GET.get('classe', '')
    recherche = request.GET.get('q', '').strip()

    inscriptions = Inscription.objects.filter(
        annee_scolaire=annee, classe__etablissement=etab, actif=True
    ).select_related('eleve', 'classe')

    if classe_id:
        inscriptions = inscriptions.filter(classe_id=classe_id)

    if recherche:
        inscriptions = inscriptions.filter(
            Q(eleve__nom__icontains=recherche) |
            Q(eleve__prenom__icontains=recherche) |
            Q(eleve__matricule__icontains=recherche)
        )

    inscriptions = inscriptions.order_by('classe__niveau', 'classe__nom', 'eleve__nom', 'eleve__prenom')

    total = inscriptions.count()
    nb_garcons = inscriptions.filter(eleve__sexe='M').count()
    nb_filles = inscriptions.filter(eleve__sexe='F').count()
    classes = Classe.objects.filter(etablissement=etab, annee_scolaire=annee).order_by('niveau', 'nom')

    return render(request, 'ecoles/eleve_liste.html', {
        'etablissement': etab, 'annee': annee,
        'inscriptions': inscriptions,
        'total': total, 'nb_garcons': nb_garcons, 'nb_filles': nb_filles,
        'classes': classes, 'classe_id': classe_id, 'recherche': recherche,
    })


@login_required
def eleve_creer(request):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.warning(request, "Créez d'abord une année scolaire.")
        return redirect('ecoles:annee_creer')

    if request.method == 'POST':
        form = EleveForm(request.POST, request.FILES, etablissement=etab)
        form_inscription = InscriptionForm(request.POST, etablissement=etab, annee_scolaire=annee)

        if form.is_valid() and form_inscription.is_valid():
            eleve = form.save(commit=False)
            eleve.etablissement = etab
            eleve.save()

            classe = form_inscription.cleaned_data.get('classe')
            if classe:
                Inscription.objects.create(eleve=eleve, classe=classe, annee_scolaire=annee, actif=True)
                messages.success(request, f"✅ Élève '{eleve.nom_complet}' créé et inscrit en {classe.nom} !")
            else:
                messages.success(request, f"✅ Élève '{eleve.nom_complet}' créé !")
            return redirect('ecoles:eleve_liste')
    else:
        form = EleveForm(etablissement=etab, initial={'matricule': _generer_matricule(etab, annee.libelle), 'nationalite': 'Togolaise'})
        form_inscription = InscriptionForm(etablissement=etab, annee_scolaire=annee)

    return render(request, 'ecoles/eleve_form.html', {
        'form': form, 'form_inscription': form_inscription,
        'etablissement': etab, 'annee': annee,
        'titre': 'Nouvel élève', 'mode': 'creer',
    })


@login_required
def eleve_detail(request, eleve_id):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    eleve = get_object_or_404(Eleve, id=eleve_id, etablissement=etab)
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    inscription = Inscription.objects.filter(eleve=eleve, annee_scolaire=annee, actif=True).first() if annee else None
    toutes_inscriptions = eleve.inscriptions.select_related('classe', 'annee_scolaire').order_by('-annee_scolaire__libelle')

    return render(request, 'ecoles/eleve_detail.html', {
        'etablissement': etab, 'annee': annee, 'eleve': eleve,
        'inscription': inscription, 'toutes_inscriptions': toutes_inscriptions,
    })


@login_required
def eleve_modifier(request, eleve_id):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    eleve = get_object_or_404(Eleve, id=eleve_id, etablissement=etab)
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()

    if request.method == 'POST':
        form = EleveForm(request.POST, request.FILES, instance=eleve, etablissement=etab)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f"✅ Élève '{eleve.nom_complet}' modifié avec succès !")
                return redirect('ecoles:eleve_liste')
            except Exception as e:
                messages.error(request, f"❌ Erreur lors de l'enregistrement : {e}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"⚠️ {field} : {error}")
    else:
        form = EleveForm(instance=eleve, etablissement=etab)

    return render(request, 'ecoles/eleve_form.html', {
        'form': form, 'form_inscription': None,
        'etablissement': etab, 'annee': annee, 'eleve': eleve,
        'titre': f'Modifier — {eleve.nom_complet}', 'mode': 'modifier',
    })


@login_required
def eleve_supprimer(request, eleve_id):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    eleve = get_object_or_404(Eleve, id=eleve_id, etablissement=etab)

    nb_notes = Note.objects.filter(eleve=eleve).count()
    if nb_notes > 0:
        messages.error(request, f"❌ Impossible de supprimer '{eleve.nom_complet}' : {nb_notes} note(s) saisie(s).")
        return redirect('ecoles:eleve_detail', eleve_id=eleve.id)

    if request.method == 'POST':
        nom = eleve.nom_complet
        eleve.delete()
        messages.success(request, f"🗑️ Élève '{nom}' supprimé.")
        return redirect('ecoles:eleve_liste')

    return render(request, 'ecoles/eleve_supprimer.html', {
        'eleve': eleve, 'etablissement': etab,
        'titre': f'Supprimer — {eleve.nom_complet}',
    })


@login_required
def eleve_inscrire(request, eleve_id):
    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    eleve = get_object_or_404(Eleve, id=eleve_id, etablissement=etab)
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()

    if not annee:
        messages.warning(request, "Aucune année scolaire active.")
        return redirect('ecoles:annee_creer')

    inscription_existante = Inscription.objects.filter(eleve=eleve, annee_scolaire=annee, actif=True).first()
    if inscription_existante:
        messages.info(request, f"L'élève est déjà inscrit en {inscription_existante.classe.nom}.")
        return redirect('ecoles:eleve_detail', eleve_id=eleve.id)

    if request.method == 'POST':
        form = InscriptionForm(request.POST, eleve=eleve, etablissement=etab, annee_scolaire=annee)
        if form.is_valid():
            classe = form.cleaned_data['classe']
            Inscription.objects.create(eleve=eleve, classe=classe, annee_scolaire=annee, actif=True)
            messages.success(request, f"✅ {eleve.nom_complet} inscrit(e) en {classe.nom} !")
            return redirect('ecoles:eleve_detail', eleve_id=eleve.id)
    else:
        form = InscriptionForm(eleve=eleve, etablissement=etab, annee_scolaire=annee)

    return render(request, 'ecoles/eleve_inscrire.html', {
        'form': form, 'eleve': eleve, 'etablissement': etab, 'annee': annee,
        'titre': f'Inscrire — {eleve.nom_complet}',
    })


# =====================================================
# EXPORT / IMPORT ÉLÈVES
# =====================================================
from django.http import HttpResponse
from datetime import datetime


@login_required
def eleve_export_excel(request):
    from core.export_import import exporter_eleves_excel

    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.error(request, "Aucune année scolaire active.")
        return redirect('ecoles:eleve_liste')

    classe_id = request.GET.get('classe', '')
    recherche = request.GET.get('q', '').strip()

    inscriptions = Inscription.objects.filter(annee_scolaire=annee, classe__etablissement=etab, actif=True).select_related('eleve', 'classe')
    if classe_id:
        inscriptions = inscriptions.filter(classe_id=classe_id)
    if recherche:
        inscriptions = inscriptions.filter(
            Q(eleve__nom__icontains=recherche) | Q(eleve__prenom__icontains=recherche) | Q(eleve__matricule__icontains=recherche)
        )

    inscriptions = inscriptions.order_by('classe__niveau', 'classe__nom', 'eleve__nom')

    output = exporter_eleves_excel(inscriptions, annee.libelle, etab.nom)
    nom_fichier = f"eleves_{etab.code}_{annee.libelle}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

    response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return response


@login_required
def eleve_export_csv(request):
    from core.export_import import exporter_eleves_csv

    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.error(request, "Aucune année scolaire active.")
        return redirect('ecoles:eleve_liste')

    classe_id = request.GET.get('classe', '')
    recherche = request.GET.get('q', '').strip()

    inscriptions = Inscription.objects.filter(annee_scolaire=annee, classe__etablissement=etab, actif=True).select_related('eleve', 'classe')
    if classe_id:
        inscriptions = inscriptions.filter(classe_id=classe_id)
    if recherche:
        inscriptions = inscriptions.filter(
            Q(eleve__nom__icontains=recherche) | Q(eleve__prenom__icontains=recherche) | Q(eleve__matricule__icontains=recherche)
        )

    inscriptions = inscriptions.order_by('classe__niveau', 'classe__nom', 'eleve__nom')

    output = exporter_eleves_csv(inscriptions)
    nom_fichier = f"eleves_{etab.code}_{annee.libelle}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

    response = HttpResponse(output.read(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return response


@login_required
def eleve_export_pdf(request):
    from core.export_import import exporter_eleves_pdf
    from core.models import ConfigurationEtablissement

    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.error(request, "Aucune année scolaire active.")
        return redirect('ecoles:eleve_liste')

    classe_id = request.GET.get('classe', '')
    recherche = request.GET.get('q', '').strip()

    inscriptions = Inscription.objects.filter(annee_scolaire=annee, classe__etablissement=etab, actif=True).select_related('eleve', 'classe')
    if classe_id:
        inscriptions = inscriptions.filter(classe_id=classe_id)
    if recherche:
        inscriptions = inscriptions.filter(
            Q(eleve__nom__icontains=recherche) | Q(eleve__prenom__icontains=recherche) | Q(eleve__matricule__icontains=recherche)
        )

    inscriptions = inscriptions.order_by('classe__niveau', 'classe__nom', 'eleve__nom')

    config = ConfigurationEtablissement.objects.filter(etablissement=etab).first()
    output = exporter_eleves_pdf(inscriptions, annee.libelle, etab.nom, config, request.user)
    nom_fichier = f"eleves_{etab.code}_{annee.libelle}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

    response = HttpResponse(output.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return response


@login_required
def eleve_modele_excel(request):
    from core.export_import import generer_modele_excel

    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')

    output = generer_modele_excel()
    nom_fichier = f"modele_import_eleves_{etab.code}.xlsx"

    response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return response


@login_required
def eleve_importer(request):
    from core.export_import import importer_eleves_excel

    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.error(request, "Aucune année scolaire active.")
        return redirect('ecoles:annee_creer')

    resultats = None
    if request.method == 'POST':
        if 'fichier' not in request.FILES:
            messages.error(request, "Aucun fichier sélectionné.")
        else:
            fichier = request.FILES['fichier']
            if not fichier.name.endswith(('.xlsx', '.xls')):
                messages.error(request, "Le fichier doit être au format Excel (.xlsx).")
            else:
                resultats = importer_eleves_excel(fichier, etab, annee)
                if resultats['succes']:
                    messages.success(request, f"✅ {len(resultats['succes'])} élève(s) importé(s) !")
                if resultats['erreurs']:
                    messages.warning(request, f"⚠️ {len(resultats['erreurs'])} ligne(s) en erreur.")

    return render(request, 'ecoles/eleve_importer.html', {
        'etablissement': etab, 'annee': annee,
        'resultats': resultats, 'titre': 'Importer des élèves',
    })


# =====================================================
# NOTES (avec filtrage par rôle)
# =====================================================
@login_required
def notes_selection(request):
    """Page de sélection : classe + matière + trimestre (filtrée selon le rôle)."""
    etab = _get_etablissement_user(request)
    if not etab:
        messages.error(request, "Aucun établissement lié à votre compte.")
        return redirect('accounts:logout')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        messages.warning(request, "Aucune année scolaire active.")
        return redirect('accounts:logout')

    est_enseignant = _get_enseignant_user(request) is not None

    # ✅ Charger les classes autorisées
    classes_autorisees = list(_get_classes_autorisees(request))

    # ✅ Charger les trimestres
    trimestres = list(
        Trimestre.objects.filter(
            etablissement=etab,
            annee_scolaire=annee.libelle
        ).order_by('numero')
    )

    if not trimestres:
        messages.warning(request, "Créez d'abord les trimestres.")
        return redirect('ecoles:trimestre_generer')

    # ✅ Charger les matières de la première classe (si dispo)
    matieres_initiales = []
    if classes_autorisees:
        matieres_initiales = list(
            _get_matieres_autorisees(request, classe=classes_autorisees[0])
        )

    # Traitement POST
    if request.method == 'POST':
        classe_id = request.POST.get('classe')
        matiere_id = request.POST.get('matiere')
        trimestre_id = request.POST.get('trimestre')

        if not (classe_id and matiere_id and trimestre_id):
            messages.error(request, "Sélectionnez classe, matière et trimestre.")
            return redirect('ecoles:notes_selection')

        classes_autorisees_ids = [c.id for c in classes_autorisees]
        if int(classe_id) not in classes_autorisees_ids:
            messages.error(request, "Classe non autorisée.")
            return redirect('ecoles:notes_selection')

        try:
            classe = Classe.objects.get(id=classe_id)
        except Classe.DoesNotExist:
            messages.error(request, "Classe introuvable.")
            return redirect('ecoles:notes_selection')

        matieres_autorisees = list(_get_matieres_autorisees(request, classe=classe))
        matieres_ids = [m.id for m in matieres_autorisees]

        if int(matiere_id) not in matieres_ids:
            messages.error(
                request,
                f"Vous n'êtes pas affecté(e) à cette matière dans la classe {classe.nom}."
            )
            return redirect('ecoles:notes_selection')

        return redirect(
            f"/ecole/notes/saisie/?classe={classe_id}&matiere={matiere_id}&trimestre={trimestre_id}"
        )

    # GET
    context = {
        'etablissement': etab,
        'annee': annee,
        'est_enseignant': est_enseignant,
        'aucune_affectation': not bool(classes_autorisees),
        'classes': classes_autorisees,
        'trimestres': trimestres,
        'matieres_initiales': matieres_initiales,
    }
    return render(request, 'ecoles/notes_selection.html', context)


@login_required
def api_matieres_par_classe(request, classe_id):
    """API JSON : matières autorisées pour une classe."""
    from django.http import JsonResponse

    classes_autorisees = _get_classes_autorisees(request)
    try:
        classe = classes_autorisees.get(id=classe_id)
    except Classe.DoesNotExist:
        return JsonResponse({'matieres': []}, status=404)

    matieres = _get_matieres_autorisees(request, classe=classe)

    return JsonResponse({
        'matieres': [
            {'id': m.id, 'nom': m.nom, 'coefficient': m.coefficient}
            for m in matieres
        ]
    })


@login_required
def notes_saisie(request):
    """Page de saisie des notes (avec vérification des permissions)."""
    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        return redirect('ecoles:annee_creer')

    classe_id = request.GET.get('classe') or request.POST.get('classe')
    matiere_id = request.GET.get('matiere') or request.POST.get('matiere')
    trimestre_id = request.GET.get('trimestre') or request.POST.get('trimestre')

    if not (classe_id and matiere_id and trimestre_id):
        messages.warning(request, "Veuillez sélectionner une classe, une matière et un trimestre.")
        return redirect('ecoles:notes_selection')

    classe = get_object_or_404(Classe, id=classe_id, etablissement=etab)
    matiere = get_object_or_404(Matiere, id=matiere_id, etablissement=etab)
    trimestre = get_object_or_404(Trimestre, id=trimestre_id, etablissement=etab)

    if not _verifier_acces_classe(request, classe):
        messages.error(request, f"Vous n'avez pas accès à la classe '{classe.nom}'.")
        return redirect('ecoles:notes_selection')

    if not _verifier_acces_matiere_classe(request, classe, matiere):
        messages.error(request, f"Vous n'enseignez pas '{matiere.nom}' dans la classe '{classe.nom}'.")
        return redirect('ecoles:notes_selection')

    matiere_classe = MatiereClasse.objects.filter(classe=classe, matiere=matiere).first()
    if not matiere_classe:
        messages.error(request, f"La matière '{matiere.nom}' n'est pas affectée à la classe '{classe.nom}'.")
        return redirect('ecoles:notes_selection')

    inscriptions = Inscription.objects.filter(
        classe=classe, annee_scolaire=annee, actif=True
    ).select_related('eleve').order_by('eleve__nom', 'eleve__prenom')

    eleves_ids = [i.eleve_id for i in inscriptions]

    if request.method == 'POST':
        if trimestre.cloture:
            messages.error(request, "Ce trimestre est clôturé. Impossible de modifier les notes.")
            return redirect('ecoles:notes_selection')

        erreurs = []
        donnees_sauvegardees = 0

        for insc in inscriptions:
            eleve = insc.eleve

            dev1_raw = request.POST.get(f'dev1_{eleve.id}', '').strip()
            dev2_raw = request.POST.get(f'dev2_{eleve.id}', '').strip()
            compo_raw = request.POST.get(f'compo_{eleve.id}', '').strip()

            dev1 = dev2 = compo = None

            try:
                if dev1_raw:
                    dev1 = Decimal(dev1_raw)
                    if dev1 < 0 or dev1 > 20:
                        erreurs.append(f"{eleve.nom_complet} : Note Dev1 invalide (0-20)")
                        continue
                if dev2_raw:
                    dev2 = Decimal(dev2_raw)
                    if dev2 < 0 or dev2 > 20:
                        erreurs.append(f"{eleve.nom_complet} : Note Dev2 invalide (0-20)")
                        continue
                if compo_raw:
                    compo = Decimal(compo_raw)
                    if compo < 0 or compo > 20:
                        erreurs.append(f"{eleve.nom_complet} : Note Compo invalide (0-20)")
                        continue
            except Exception:
                erreurs.append(f"{eleve.nom_complet} : Format de note invalide")
                continue

            if dev1 is None and dev2 is None and compo is None:
                Note.objects.filter(eleve=eleve, matiere=matiere, trimestre=trimestre).delete()
                donnees_sauvegardees += 1
                continue

            Note.objects.update_or_create(
                eleve=eleve, matiere=matiere, trimestre=trimestre,
                defaults={
                    'note_devoir1': dev1,
                    'note_devoir2': dev2,
                    'note_composition': compo,
                    'enseignant': matiere_classe.enseignant,
                }
            )
            donnees_sauvegardees += 1

        if erreurs:
            for err in erreurs[:10]:
                messages.error(request, err)
        else:
            messages.success(request, f"✅ Notes enregistrées ! ({donnees_sauvegardees} élève(s))")
        return redirect('ecoles:notes_selection')

    notes_existantes = {
        n.eleve_id: n for n in Note.objects.filter(
            eleve_id__in=eleves_ids,
            matiere=matiere,
            trimestre=trimestre,
        )
    }

    def fmt(val):
        if val is None:
            return ''
        try:
            f = float(val)
            if f == int(f):
                return str(int(f))
            return str(f)
        except Exception:
            return str(val)

    eleves_data = []
    for insc in inscriptions:
        eleve = insc.eleve
        note = notes_existantes.get(eleve.id)
        eleves_data.append({
            'eleve': eleve,
            'matricule': eleve.matricule,
            'nom': eleve.nom,
            'prenom': eleve.prenom,
            'sexe': eleve.sexe,
            'dev1_str': fmt(note.note_devoir1) if note else '',
            'dev2_str': fmt(note.note_devoir2) if note else '',
            'compo_str': fmt(note.note_composition) if note else '',
            'moy_devoirs': note.moyenne_devoirs if note else None,
            'moy_finale': note.moyenne_finale if note else None,
        })

    est_enseignant = _get_enseignant_user(request) is not None

    return render(request, 'ecoles/notes_saisie.html', {
        'etablissement': etab,
        'annee': annee,
        'classe': classe,
        'matiere': matiere,
        'trimestre': trimestre,
        'matiere_classe': matiere_classe,
        'eleves_data': eleves_data,
        'nb_eleves': len(eleves_data),
        'est_enseignant': est_enseignant,
    })


@login_required
def notes_verification(request):
    """Tableau global de vérification (avec filtrage par rôle)."""
    etab = _get_etablissement_user(request)
    if not etab:
        return redirect('dashboard:redirection')

    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()
    if not annee:
        return redirect('ecoles:annee_creer')

    classes_autorisees = _get_classes_autorisees(request)

    if not classes_autorisees.exists():
        if _get_enseignant_user(request):
            messages.warning(request, "Aucune classe ne vous est affectée.")
        else:
            messages.warning(request, "Créez d'abord des classes.")
        return redirect('dashboard:redirection')

    classe_id = request.GET.get('classe')
    trimestre_id = request.GET.get('trimestre')

    if not classe_id:
        trimestres = Trimestre.objects.filter(etablissement=etab, annee_scolaire=annee.libelle).order_by('numero')
        est_enseignant = _get_enseignant_user(request) is not None
        return render(request, 'ecoles/notes_verification_selection.html', {
            'etablissement': etab, 'annee': annee,
            'classes': classes_autorisees,
            'trimestres': trimestres,
            'classe_id': '', 'trimestre_id': '',
            'est_enseignant': est_enseignant,
        })

    classe = get_object_or_404(Classe, id=classe_id, etablissement=etab)

    if not _verifier_acces_classe(request, classe):
        messages.error(request, f"Vous n'avez pas accès à la classe '{classe.nom}'.")
        return redirect('ecoles:notes_verification')

    if not trimestre_id:
        trimestre = Trimestre.objects.filter(etablissement=etab, annee_scolaire=annee.libelle).order_by('numero').first()
    else:
        trimestre = get_object_or_404(Trimestre, id=trimestre_id, etablissement=etab)

    if not trimestre:
        messages.warning(request, "Créez d'abord les trimestres.")
        return redirect('ecoles:trimestre_generer')

    enseignant = _get_enseignant_user(request)
    if enseignant:
        matieres_classe = MatiereClasse.objects.filter(
            classe=classe, enseignant=enseignant
        ).select_related('matiere').order_by('matiere__ordre', 'matiere__nom')
    else:
        matieres_classe = MatiereClasse.objects.filter(classe=classe).select_related('matiere').order_by('matiere__ordre', 'matiere__nom')

    inscriptions = Inscription.objects.filter(classe=classe, annee_scolaire=annee, actif=True).select_related('eleve').order_by('eleve__nom', 'eleve__prenom')

    eleves_data = []
    matieres_list = [mc.matiere for mc in matieres_classe]

    for insc in inscriptions:
        eleve = insc.eleve
        notes_eleve = Note.objects.filter(
            eleve=eleve,
            matiere__in=matieres_list,
            trimestre=trimestre,
        )
        notes_par_matiere = {n.matiere_id: n for n in notes_eleve}

        total_points = Decimal('0')
        somme_coefficients = Decimal('0')
        notes_detail = []

        for mc in matieres_classe:
            note = notes_par_matiere.get(mc.matiere_id)
            moyf = note.moyenne_finale if note else None
            coef = mc.coefficient

            if moyf is not None:
                total_points += Decimal(str(moyf)) * Decimal(str(coef))
                somme_coefficients += Decimal(str(coef))

            notes_detail.append({
                'matiere': mc.matiere,
                'coefficient': coef,
                'moyf': moyf,
            })

        moyenne_trimestre = None
        if somme_coefficients > 0:
            moyenne_trimestre = round(float(total_points / somme_coefficients), 2)

        eleves_data.append({
            'eleve': eleve,
            'notes_detail': notes_detail,
            'total_points': float(total_points),
            'moyenne_trimestre': moyenne_trimestre,
        })

    if not enseignant:
        eleves_avec_moyenne = [e for e in eleves_data if e['moyenne_trimestre'] is not None]
        eleves_avec_moyenne.sort(key=lambda x: x['moyenne_trimestre'], reverse=True)
        for i, eleve_data in enumerate(eleves_avec_moyenne):
            if i > 0 and eleve_data['moyenne_trimestre'] == eleves_avec_moyenne[i-1]['moyenne_trimestre']:
                eleve_data['rang'] = eleves_avec_moyenne[i-1]['rang']
            else:
                eleve_data['rang'] = i + 1

    for eleve_data in eleves_data:
        moy = eleve_data['moyenne_trimestre']
        if moy is None:
            eleve_data['appreciation'] = '—'
        elif moy < 8:
            eleve_data['appreciation'] = 'Faible'
        elif moy < 10:
            eleve_data['appreciation'] = 'Passable'
        elif moy < 12:
            eleve_data['appreciation'] = 'Assez bien'
        elif moy < 14:
            eleve_data['appreciation'] = 'Bien'
        else:
            eleve_data['appreciation'] = 'Très bien'

    eleves_data.sort(key=lambda x: (x['eleve'].nom, x['eleve'].prenom))

    est_enseignant = enseignant is not None

    return render(request, 'ecoles/notes_verification.html', {
        'etablissement': etab, 'annee': annee,
        'classe': classe, 'trimestre': trimestre,
        'matieres_classe': matieres_classe,
        'eleves_data': eleves_data, 'nb_eleves': len(eleves_data),
        'classe_id': classe_id, 'trimestre_id': trimestre_id,
        'classes': classes_autorisees,
        'trimestres': Trimestre.objects.filter(etablissement=etab, annee_scolaire=annee.libelle).order_by('numero'),
        'est_enseignant': est_enseignant,
    })


# =====================================================
# VÉRIFICATION DE LA CONFIGURATION (Session 16)
# =====================================================
@login_required
def verification_config(request):
    """
    Page de vérification de l'état de la configuration de l'établissement.
    Affiche une checklist avec badges ✅ / ❌ / ⚠️ et un pourcentage global.
    """
    from core.models import (
        ConfigurationEtablissement, AnneeScolaire, Trimestre,
        Classe, Matiere, MatiereClasse,
    )

    etab = _get_etablissement_chef(request)
    if not etab:
        return redirect('dashboard:redirection')

    config, _ = ConfigurationEtablissement.objects.get_or_create(etablissement=etab)

    # ===== Année en cours =====
    annee = AnneeScolaire.objects.filter(etablissement=etab, en_cours=True).first()

    # ===== Statistiques =====
    nb_trimestres = 0
    if annee:
        nb_trimestres = Trimestre.objects.filter(
            etablissement=etab, annee_scolaire=annee.libelle
        ).count()

    nb_classes = 0
    nb_matieres = 0
    nb_matieres_affectees = 0
    if annee:
        nb_classes = Classe.objects.filter(etablissement=etab, annee_scolaire=annee).count()
        nb_matieres = Matiere.objects.filter(etablissement=etab, annee_scolaire=annee).count()
        nb_matieres_affectees = MatiereClasse.objects.filter(
            classe__etablissement=etab, classe__annee_scolaire=annee
        ).count()

    # ===== Fonction utilitaire pour un item =====
    def _item(label, valeur, statut, lien_url, lien_label, icone):
        """
        statut : 'ok' (vert) / 'partiel' (orange) / 'manquant' (rouge)
        """
        return {
            'label': label,
            'valeur': valeur,
            'statut': statut,
            'lien_url': lien_url,
            'lien_label': lien_label,
            'icone': icone,
        }

    items = []

    # --- 1. Logo établissement ---
    has_logo = bool(etab.logo)
    items.append(_item(
        "Logo de l'établissement",
        "Présent" if has_logo else "Absent",
        'ok' if has_logo else 'manquant',
        '/ecole/configuration/',
        'Configurer',
        'bi-image',
    ))

    # --- 2. Nom officiel + Devise école ---
    nom_ok = bool(config.nom_officiel)
    devise_ok = bool(config.devise_ecole)
    if nom_ok and devise_ok:
        statut = 'ok'
        valeur = "Complet"
    elif nom_ok or devise_ok:
        statut = 'partiel'
        valeur = f"Nom : {'✓' if nom_ok else '✗'} · Devise : {'✓' if devise_ok else '✗'}"
    else:
        statut = 'manquant'
        valeur = "Absent"
    items.append(_item(
        "Nom officiel + Devise école",
        valeur,
        statut,
        '/ecole/configuration/',
        'Configurer',
        'bi-file-text',
    ))

    # --- 3. Ministère / Direction / Inspection ---
    m_ok = bool(config.ministere)
    d_ok = bool(config.direction_regionale)
    i_ok = bool(config.inspection)
    nb_ok = sum([m_ok, d_ok, i_ok])
    if nb_ok == 3:
        statut = 'ok'; valeur = "Complet"
    elif nb_ok > 0:
        statut = 'partiel'; valeur = f"{nb_ok}/3 renseignés"
    else:
        statut = 'manquant'; valeur = "Absent"
    items.append(_item(
        "Ministère / Direction / Inspection",
        valeur,
        statut,
        '/ecole/configuration/',
        'Configurer',
        'bi-bank',
    ))

    # --- 4. Préfecture / Commune admin. / Périmètre ---
    p_ok = bool(config.prefecture)
    c_ok = bool(config.commune_administration)
    per_ok = bool(config.perimetre_pedagogique)
    nb_ok = sum([p_ok, c_ok, per_ok])
    if nb_ok == 3:
        statut = 'ok'; valeur = "Complet"
    elif nb_ok > 0:
        statut = 'partiel'; valeur = f"{nb_ok}/3 renseignés"
    else:
        statut = 'manquant'; valeur = "Absent"
    items.append(_item(
        "Préfecture / Commune / Périmètre",
        valeur,
        statut,
        '/ecole/configuration/',
        'Configurer',
        'bi-geo-alt',
    ))

    # --- 5. Nom du chef + Titre ---
    n_ok = bool(config.nom_chef)
    t_ok = bool(config.titre_chef)
    if n_ok and t_ok:
        statut = 'ok'; valeur = "Complet"
    elif n_ok or t_ok:
        statut = 'partiel'; valeur = f"Nom : {'✓' if n_ok else '✗'} · Titre : {'✓' if t_ok else '✗'}"
    else:
        statut = 'manquant'; valeur = "Absent"
    items.append(_item(
        "Nom du chef + Titre du chef",
        valeur,
        statut,
        '/ecole/configuration/',
        'Configurer',
        'bi-person-badge',
    ))

    # --- 6. Signature du chef ---
    sig_ok = bool(config.signature_chef)
    items.append(_item(
        "Signature du chef (image)",
        "Présente" if sig_ok else "Absente",
        'ok' if sig_ok else 'manquant',
        '/ecole/configuration/',
        'Configurer',
        'bi-pen',
    ))

    # --- 7. Cachet de l'école ---
    cachet_ok = bool(config.cachet_ecole)
    items.append(_item(
        "Cachet de l'école (image)",
        "Présent" if cachet_ok else "Absent",
        'ok' if cachet_ok else 'manquant',
        '/ecole/configuration/',
        'Configurer',
        'bi-award',
    ))

    # --- 8. Année scolaire active ---
    annee_ok = bool(annee)
    items.append(_item(
        "Année scolaire active",
        annee.libelle if annee_ok else "Aucune",
        'ok' if annee_ok else 'manquant',
        '/ecole/annees/',
        'Gérer les années',
        'bi-calendar-event',
    ))

    # --- 9. Trimestres créés (>= 3) ---
    if nb_trimestres >= 3:
        statut = 'ok'; valeur = f"{nb_trimestres} trimestres"
    elif nb_trimestres > 0:
        statut = 'partiel'; valeur = f"{nb_trimestres}/3 créés"
    else:
        statut = 'manquant'; valeur = "Aucun"
    items.append(_item(
        "Trimestres créés (≥ 3)",
        valeur,
        statut,
        '/ecole/trimestres/',
        'Gérer les trimestres',
        'bi-calendar3',
    ))

    # --- 10. Classes créées ---
    if nb_classes > 0:
        statut = 'ok'; valeur = f"{nb_classes} classes"
    else:
        statut = 'manquant'; valeur = "Aucune"
    items.append(_item(
        "Classes créées",
        valeur,
        statut,
        '/ecole/classes/',
        'Gérer les classes',
        'bi-mortarboard',
    ))

    # --- 11. Matières créées ---
    if nb_matieres > 0:
        statut = 'ok'; valeur = f"{nb_matieres} matières"
    else:
        statut = 'manquant'; valeur = "Aucune"
    items.append(_item(
        "Matières créées",
        valeur,
        statut,
        '/ecole/matieres/',
        'Gérer les matières',
        'bi-book',
    ))

    # --- 12. Matières affectées aux classes ---
    if nb_matieres_affectees > 0:
        statut = 'ok'; valeur = f"{nb_matieres_affectees} affectations"
    else:
        statut = 'manquant'; valeur = "Aucune"
    items.append(_item(
        "Matières affectées aux classes",
        valeur,
        statut,
        '/ecole/matieres-classes/',
        'Gérer les affectations',
        'bi-diagram-3',
    ))

    # ===== Calcul du pourcentage global =====
    # Score : 1.0 pour 'ok', 0.5 pour 'partiel', 0.0 pour 'manquant'
    score = 0.0
    for it in items:
        if it['statut'] == 'ok':
            score += 1.0
        elif it['statut'] == 'partiel':
            score += 0.5
    pourcentage = round((score / len(items)) * 100, 1) if items else 0.0

    # Nombre d'items total, ok, partiels, manquants
    nb_total = len(items)
    nb_ok = sum(1 for it in items if it['statut'] == 'ok')
    nb_partiel = sum(1 for it in items if it['statut'] == 'partiel')
    nb_manquant = sum(1 for it in items if it['statut'] == 'manquant')

    context = {
        'etablissement': etab,
        'config': config,
        'annee': annee,
        'items': items,
        'pourcentage': pourcentage,
        'nb_total': nb_total,
        'nb_ok': nb_ok,
        'nb_partiel': nb_partiel,
        'nb_manquant': nb_manquant,
        'titre': 'Vérification de la configuration',
    }
    return render(request, 'ecoles/verification_config.html', context)
