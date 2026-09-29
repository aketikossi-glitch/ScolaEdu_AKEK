from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout


class RestrictionAdminDjangoMiddleware:
    """Interdit l'accès à /admin/ aux non-admin-principaux."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            if not request.user.is_authenticated:
                return self.get_response(request)
            if request.user.is_superuser:
                return self.get_response(request)
            try:
                role = request.user.profil.role
                if role != 'admin_principal':
                    messages.warning(
                        request,
                        "Accès à l'administration technique refusé. Utilisez votre espace ScolaEdu_AKEK."
                    )
                    return redirect('dashboard:redirection')
            except Exception:
                messages.error(request, "Votre compte n'a pas de profil valide.")
                return redirect('accounts:logout')
        return self.get_response(request)


class VerificationEtablissementActifMiddleware:
    """
    Vérifie que l'établissement de l'utilisateur est actif.
    Si suspendu, déconnecte l'utilisateur avec un message explicite.
    """

    # ⚠️ Chemins EXACTS à ne PAS vérifier (pas de '/' tout seul !)
    EXEMPT_EXACT = {
        '/',
        '/auth/login/',
        '/auth/logout/',
        '/admin/',
    }
    EXEMPT_PREFIXES = (
        '/static/',
        '/media/',
        '/admin/',
        '/auth/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Exempter les chemins exacts
        if path in self.EXEMPT_EXACT:
            return self.get_response(request)

        # Exempter les préfixes
        if path.startswith(self.EXEMPT_PREFIXES):
            return self.get_response(request)

        # À partir d'ici : on est sur une page interne
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Admin Principal : jamais bloqué
        try:
            profil = request.user.profil
        except Exception:
            return self.get_response(request)

        if profil.role == 'admin_principal':
            return self.get_response(request)

        # Vérifier que l'établissement est actif
        etab = profil.etablissement
        if etab and not etab.actif:
            raison = etab.raison_suspension or "Contactez l'administrateur principal pour plus d'informations."
            logout(request)
            messages.error(
                request,
                f"🚫 L'établissement « {etab.nom} » ({etab.code}) est actuellement suspendu. {raison}"
            )
            return redirect('accounts:login')

        return self.get_response(request)
