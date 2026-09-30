#!/bin/bash

set -o errexit

echo "========================================"
echo "ScolaEdu_AKEK - BUILD DE PRODUCTION"
echo "========================================"

echo ">>> Installation des dépendances..."
python -m pip install -r requirements-prod.txt

echo ">>> Vérification Django..."
python manage.py check

echo ">>> Collecte des fichiers statiques..."
python manage.py collectstatic --noinput

echo ">>> Application des migrations..."
python manage.py migrate --noinput

echo ">>> Création du superutilisateur + profil (si inexistant)..."
python manage.py shell << 'PYEOF'
from django.contrib.auth.models import User
from core.models import ProfilUtilisateur
import os

username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@scolaedu.tg')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')

if not password:
    print("Superutilisateur : mot de passe non defini (variables manquantes)")
else:
    # 1. Créer ou récupérer le User
    user, created = User.objects.get_or_create(
        username=username,
        defaults={'email': email, 'is_staff': True, 'is_superuser': True}
    )
    if created:
        user.set_password(password)
        user.save()
        print(f"Utilisateur '{username}' cree")

    # 2. Créer ou mettre à jour le ProfilUtilisateur
    profil, profil_created = ProfilUtilisateur.objects.get_or_create(
        user=user,
        defaults={'role': 'admin_principal'}
    )
    if profil_created:
        print(f"Profil 'admin_principal' cree pour '{username}'")
    else:
        # S'assurer que le rôle est bien admin_principal
        if profil.role != 'admin_principal':
            profil.role = 'admin_principal'
            profil.etablissement = None
            profil.save()
            print(f"Profil mis a jour : role = admin_principal")
        else:
            print(f"Profil '{username}' deja existant (admin_principal)")
PYEOF

echo "========================================"
echo "BUILD TERMINE AVEC SUCCES"
echo "========================================"
