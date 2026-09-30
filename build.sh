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

echo ">>> Création du superutilisateur (si inexistant)..."
python manage.py shell << 'PYEOF'
from django.contrib.auth.models import User
import os

username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@scolaedu.tg')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')

if password and not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Superutilisateur '{username}' cree")
else:
    print(f"Superutilisateur '{username}' deja existant ou mot de passe non defini")
PYEOF

echo "========================================"
echo "BUILD TERMINE AVEC SUCCES"
echo "========================================"
