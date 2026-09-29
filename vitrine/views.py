from django.shortcuts import render


def accueil(request):
    """Page d'accueil publique de ScolaEdu_AKEK."""
    return render(request, 'vitrine/accueil.html')
