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

echo "========================================"
echo "BUILD TERMINÉ AVEC SUCCÈS"
echo "========================================"
