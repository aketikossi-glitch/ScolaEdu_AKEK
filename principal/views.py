from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from core.models import (
    Etablissement, ProfilUtilisateur, AnneeScolaire,
    Classe, Eleve, Enseignant, Note
)
from .forms import (
    CreerEtablissementForm, ModifierEtablissementForm,
    AjouterUtilisateurForm, ModifierUtilisateurForm,
    ResetPasswordForm, generer_mot_de_passe
)


def _verif_admin_principal(request):
    try:
        return request.user.profil.role == 'admin_principal'
    except Exception:
        return False


# =====================================================
# ÉTABLISSEMENTS
# =====================================================

@login_required
def etablissement_liste(request):
    if not _verif_admin_principal(request):
        messages.error(request, "Accès réservé à l'administrateur principal.")
        return redirect('dashboard:redirection')

    filtre = request.GET.get('filtre', 'tous')
    qs = Etablissement.objects.all().order_by('-date_creation')
    if filtre == 'actifs':
        qs = qs.filter(actif=True)
    elif filtre == 'suspendus':
        qs = qs.filter(actif=False)

    data = []
    for etab in qs:
        chef = ProfilUtilisateur.objects.filter(
            etablissement=etab, role='chef_etablissement'
        ).select_related('user').first()

        data.append({
            'etablissement': etab,
            'chef': chef.user if chef else None,
            'nb_utilisateurs': ProfilUtilisateur.objects.filter(etablissement=etab).count(),
            'annee_active': AnneeScolaire.objects.filter(
                etablissement=etab, en_cours=True
            ).first(),
            'est_vide': etab.est_vide(),
        })

    context = {
        'titre': 'Établissements',
        'data': data,
        'total': Etablissement.objects.count(),
        'total_actifs': Etablissement.objects.filter(actif=True).count(),
        'total_suspendus': Etablissement.objects.filter(actif=False).count(),
        'filtre': filtre,
    }
    return render(request, 'principal/etablissement_liste.html', context)


@login_required
def etablissement_creer(request):
    if not _verif_admin_principal(request):
        messages.error(request, "Accès réservé à l'administrateur principal.")
        return redirect('dashboard:redirection')

    if request.method == 'POST':
        form = CreerEtablissementForm(request.POST)
        if form.is_valid():
            etablissement, chef, mot_de_passe = form.save()
            request.session['nouveau_chef_infos'] = {
                'etablissement': etablissement.nom,
                'username': chef.username,
                'password': mot_de_passe,
                'email': chef.email,
            }
            messages.success(
                request,
                f"✅ Établissement '{etablissement.nom}' et compte du chef créés avec succès !"
            )
            return redirect('principal:etablissement_creer_succes')
    else:
        form = CreerEtablissementForm()

    return render(request, 'principal/etablissement_creer.html', {
        'form': form,
        'titre': 'Créer un établissement',
    })


@login_required
def etablissement_creer_succes(request):
    if not _verif_admin_principal(request):
        return redirect('dashboard:redirection')

    infos = request.session.pop('nouveau_chef_infos', None)
    if not infos:
        messages.warning(request, "Aucune création récente.")
        return redirect('principal:etablissement_liste')

    return render(request, 'principal/etablissement_creer_succes.html', {
        'titre': 'Création réussie',
        'infos': infos,
    })


@login_required
def etablissement_detail(request, etab_id):
    if not _verif_admin_principal(request):
        return redirect('dashboard:redirection')

    etablissement = get_object_or_404(Etablissement, id=etab_id)
    utilisateurs = ProfilUtilisateur.objects.filter(
        etablissement=etablissement
    ).select_related('user').order_by('role', 'user__last_name')

    annees = AnneeScolaire.objects.filter(
        etablissement=etablissement
    ).order_by('-libelle')

    context = {
        'titre': f'{etablissement.nom}',
        'etablissement': etablissement,
        'utilisateurs': utilisateurs,
        'annees': annees,
        'est_vide': etablissement.est_vide(),
    }
    return render(request, 'principal/etablissement_detail.html', context)


@login_required
def etablissement_modifier(request, etab_id):
    if not _verif_admin_principal(request):
        return redirect('dashboard:redirection')

    etablissement = get_object_or_404(Etablissement, id=etab_id)

    if request.method == 'POST':
        form = ModifierEtablissementForm(
            request.POST, request.FILES, instance=etablissement
        )
        if form.is_valid():
            nouveau_code = form.cleaned_data['code']
            if Etablissement.objects.filter(code=nouveau_code).exclude(pk=etablissement.pk).exists():
                messages.error(request, f"Le code '{nouveau_code}' est déjà utilisé par un autre établissement.")
            else:
                form.save()
                messages.success(request, f"✅ Établissement '{etablissement.nom}' modifié avec succès !")
                return redirect('principal:etablissement_detail', etab_id=etablissement.id)
    else:
        form = ModifierEtablissementForm(instance=etablissement)

    return render(request, 'principal/etablissement_modifier.html', {
        'form': form,
        'etablissement': etablissement,
        'titre': f'Modifier — {etablissement.nom}',
    })


@login_required
def etablissement_suspendre(request, etab_id):
    if not _verif_admin_principal(request):
        return redirect('dashboard:redirection')

    etablissement = get_object_or_404(Etablissement, id=etab_id)

    if request.method == 'POST':
        raison = request.POST.get('raison', '').strip()
        etablissement.actif = False
        etablissement.raison_suspension = raison
        etablissement.date_suspension = timezone.now()
        etablissement.save()
        messages.warning(
            request,
            f"⏸️ L'établissement '{etablissement.nom}' a été suspendu. "
            f"Ses utilisateurs ne peuvent plus se connecter."
        )
        return redirect('principal:etablissement_liste')

    return render(request, 'principal/etablissement_suspendre.html', {
        'etablissement': etablissement,
        'titre': f'Suspendre — {etablissement.nom}',
    })


@login_required
def etablissement_activer(request, etab_id):
    if not _verif_admin_principal(request):
        return redirect('dashboard:redirection')

    etablissement = get_object_or_404(Etablissement, id=etab_id)
    etablissement.actif = True
    etablissement.raison_suspension = ''
    etablissement.date_suspension = None
    etablissement.save()
    messages.success(
        request,
        f"✅ L'établissement '{etablissement.nom}' a été réactivé."
    )
    return redirect('principal:etablissement_liste')


@login_required
def etablissement_supprimer(request, etab_id):
    if not _verif_admin_principal(request):
        return redirect('dashboard:redirection')

    etablissement = get_object_or_404(Etablissement, id=etab_id)

    if not etablissement.est_vide():
        messages.error(
            request,
            f"❌ Impossible de supprimer '{etablissement.nom}' : il contient des données métier."
        )
        return redirect('principal:etablissement_liste')

    if request.method == 'POST':
        code_confirmation = request.POST.get('code_confirmation', '').strip()
        if code_confirmation != etablissement.code:
            messages.error(request, f"Le code saisi ne correspond pas.")
            return redirect('principal:etablissement_supprimer', etab_id=etablissement.id)

        nom = etablissement.nom
        for profil in ProfilUtilisateur.objects.filter(etablissement=etablissement):
            user = profil.user
            profil.delete()
            user.delete()
        etablissement.delete()

        messages.success(request, f"🗑️ Établissement '{nom}' supprimé définitivement.")
        return redirect('principal:etablissement_liste')

    return render(request, 'principal/etablissement_supprimer.html', {
        'etablissement': etablissement,
        'titre': f'Supprimer — {etablissement.nom}',
    })


# =====================================================
# UTILISATEURS D'UN ÉTABLISSEMENT
# =====================================================

@login_required
def utilisateur_ajouter(request, etab_id):
    """Ajouter un utilisateur à un établissement."""
    if not _verif_admin_principal(request):
        return redirect('dashboard:redirection')

    etablissement = get_object_or_404(Etablissement, id=etab_id)

    if request.method == 'POST':
        form = AjouterUtilisateurForm(request.POST, etablissement=etablissement)
        if form.is_valid():
            user, mot_de_passe = form.save()
            request.session['nouvel_utilisateur_infos'] = {
                'etablissement': etablissement.nom,
                'username': user.username,
                'password': mot_de_passe,
                'email': user.email,
                'role': user.profil.get_role_display(),
            }
            messages.success(request, f"✅ Utilisateur '{user.username}' créé avec succès !")
            return redirect('principal:utilisateur_ajouter_succes', etab_id=etablissement.id)
    else:
        form = AjouterUtilisateurForm(etablissement=etablissement)

    return render(request, 'principal/utilisateur_ajouter.html', {
        'form': form,
        'etablissement': etablissement,
        'titre': f'Ajouter un utilisateur — {etablissement.nom}',
    })


@login_required
def utilisateur_ajouter_succes(request, etab_id):
    if not _verif_admin_principal(request):
        return redirect('dashboard:redirection')

    etablissement = get_object_or_404(Etablissement, id=etab_id)
    infos = request.session.pop('nouvel_utilisateur_infos', None)
    if not infos:
        return redirect('principal:etablissement_detail', etab_id=etablissement.id)

    return render(request, 'principal/utilisateur_ajouter_succes.html', {
        'titre': 'Utilisateur créé',
        'infos': infos,
        'etablissement': etablissement,
    })


@login_required
def utilisateur_modifier(request, profil_id):
    """Modifier un utilisateur."""
    if not _verif_admin_principal(request):
        return redirect('dashboard:redirection')

    profil = get_object_or_404(ProfilUtilisateur, id=profil_id)
    etablissement = profil.etablissement

    if request.method == 'POST':
        form = ModifierUtilisateurForm(request.POST, profil=profil)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Utilisateur modifié avec succès.")
            return redirect('principal:etablissement_detail', etab_id=etablissement.id)
    else:
        form = ModifierUtilisateurForm(profil=profil)

    return render(request, 'principal/utilisateur_modifier.html', {
        'form': form,
        'profil': profil,
        'etablissement': etablissement,
        'titre': f'Modifier — {profil.user.username}',
    })


@login_required
def utilisateur_desactiver(request, profil_id):
    """Désactiver un utilisateur (sauf soi-même et le chef)."""
    if not _verif_admin_principal(request):
        return redirect('dashboard:redirection')

    profil = get_object_or_404(ProfilUtilisateur, id=profil_id)
    etablissement = profil.etablissement

    if profil.role == 'chef_etablissement':
        messages.error(request, "Impossible de désactiver le chef d'établissement.")
        return redirect('principal:etablissement_detail', etab_id=etablissement.id)

    profil.user.is_active = False
    profil.user.save()
    messages.warning(request, f"⏸️ Utilisateur '{profil.user.username}' désactivé.")
    return redirect('principal:etablissement_detail', etab_id=etablissement.id)


@login_required
def utilisateur_activer(request, profil_id):
    """Réactiver un utilisateur."""
    if not _verif_admin_principal(request):
        return redirect('dashboard:redirection')

    profil = get_object_or_404(ProfilUtilisateur, id=profil_id)
    profil.user.is_active = True
    profil.user.save()
    messages.success(request, f"✅ Utilisateur '{profil.user.username}' réactivé.")
    return redirect('principal:etablissement_detail', etab_id=profil.etablissement.id)


@login_required
def utilisateur_supprimer(request, profil_id):
    """Supprimer un utilisateur (sauf chef)."""
    if not _verif_admin_principal(request):
        return redirect('dashboard:redirection')

    profil = get_object_or_404(ProfilUtilisateur, id=profil_id)
    etablissement = profil.etablissement

    if profil.role == 'chef_etablissement':
        messages.error(request, "Impossible de supprimer le chef d'établissement.")
        return redirect('principal:etablissement_detail', etab_id=etablissement.id)

    if request.method == 'POST':
        username = profil.user.username
        user = profil.user
        profil.delete()
        user.delete()
        messages.success(request, f"🗑️ Utilisateur '{username}' supprimé.")
        return redirect('principal:etablissement_detail', etab_id=etablissement.id)

    return render(request, 'principal/utilisateur_supprimer.html', {
        'profil': profil,
        'etablissement': etablissement,
        'titre': f'Supprimer — {profil.user.username}',
    })


@login_required
def utilisateur_reset_password(request, profil_id):
    """Réinitialiser le mot de passe d'un utilisateur."""
    if not _verif_admin_principal(request):
        return redirect('dashboard:redirection')

    profil = get_object_or_404(ProfilUtilisateur, id=profil_id)

    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            nouveau = form.cleaned_data.get('nouveau_mot_de_passe') or generer_mot_de_passe()
            profil.user.set_password(nouveau)
            profil.user.save()
            request.session['reset_password_infos'] = {
                'username': profil.user.username,
                'password': nouveau,
            }
            messages.success(request, f"🔑 Mot de passe réinitialisé.")
            return redirect('principal:utilisateur_reset_succes', profil_id=profil.id)
    else:
        form = ResetPasswordForm()

    return render(request, 'principal/utilisateur_reset_password.html', {
        'form': form,
        'profil': profil,
        'etablissement': profil.etablissement,
        'titre': f'Réinitialiser mot de passe — {profil.user.username}',
    })


@login_required
def utilisateur_reset_succes(request, profil_id):
    if not _verif_admin_principal(request):
        return redirect('dashboard:redirection')

    profil = get_object_or_404(ProfilUtilisateur, id=profil_id)
    infos = request.session.pop('reset_password_infos', None)
    if not infos:
        return redirect('principal:etablissement_detail', etab_id=profil.etablissement.id)

    return render(request, 'principal/utilisateur_reset_succes.html', {
        'titre': 'Mot de passe réinitialisé',
        'infos': infos,
        'profil': profil,
        'etablissement': profil.etablissement,
    })


# =====================================================
# LISTE GLOBALE
# =====================================================

@login_required
def utilisateur_liste_globale(request):
    if not _verif_admin_principal(request):
        return redirect('dashboard:redirection')

    utilisateurs = ProfilUtilisateur.objects.all().select_related(
        'user', 'etablissement'
    ).order_by('etablissement__nom', 'role', 'user__last_name')

    context = {
        'titre': 'Tous les utilisateurs',
        'utilisateurs': utilisateurs,
    }
    return render(request, 'principal/utilisateur_liste.html', context)
