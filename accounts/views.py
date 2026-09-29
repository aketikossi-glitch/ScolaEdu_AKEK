from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from core.models import ProfilUtilisateur


def login_view(request):
    """Page de connexion ScolaEdu_AKEK."""

    # Si déjà connecté, rediriger selon le rôle
    if request.user.is_authenticated:
        return redirect('dashboard:redirection')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f"Bienvenue, {user.get_full_name() or user.username} !")
            return redirect('dashboard:redirection')
        else:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")

    return render(request, 'accounts/login.html')


def logout_view(request):
    """Déconnexion de l'utilisateur."""
    logout(request)
    messages.info(request, "Vous avez été déconnecté.")
    return redirect('vitrine:accueil')
