"""
Configuration Django du projet ScolaEdu_AKEK.

Compatible avec :
- développement local sous Termux / Android avec SQLite ;
- déploiement en production avec PostgreSQL ;
- Render ;
- fichiers statiques avec WhiteNoise ;
- fichiers médias des établissements et des élèves.
"""

import os
from pathlib import Path

import dj_database_url


# =============================================================================
# CHEMINS DU PROJET
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# =============================================================================
# SÉCURITÉ
# =============================================================================

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-dev-only-change-this-key-before-production",
)

DEBUG = os.environ.get("DEBUG", "True").lower() in ("true", "1", "yes")


def liste_env(nom, valeur_defaut=""):
    """
    Transforme une variable d'environnement séparée par des virgules
    en liste Python.
    """
    valeur = os.environ.get(nom, valeur_defaut)
    return [element.strip() for element in valeur.split(",") if element.strip()]


ALLOWED_HOSTS = liste_env(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost,0.0.0.0",
)

# Render fournit le nom d'hôte externe dans cette variable.
render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")

if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)


CSRF_TRUSTED_ORIGINS = liste_env("CSRF_TRUSTED_ORIGINS")


# =============================================================================
# APPLICATIONS
# =============================================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "core",
    "accounts",
    "dashboard",
    "ecoles",
    "vitrine",
    "principal",
]


# =============================================================================
# MIDDLEWARE
# =============================================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    # WhiteNoise sert les fichiers statiques en production.
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    "accounts.middleware.RestrictionAdminDjangoMiddleware",
    "accounts.middleware.VerificationEtablissementActifMiddleware",
]


ROOT_URLCONF = "gestion_ecole.urls"


# =============================================================================
# TEMPLATES
# =============================================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


WSGI_APPLICATION = "gestion_ecole.wsgi.application"


# =============================================================================
# BASE DE DONNÉES
# =============================================================================

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=not DEBUG,
        )
    }
else:
    # Développement local sous Termux.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# =============================================================================
# VALIDATION DES MOTS DE PASSE
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# =============================================================================
# INTERNATIONALISATION
# =============================================================================

LANGUAGE_CODE = "fr-fr"

TIME_ZONE = "Africa/Lome"

USE_I18N = True

USE_TZ = True


# =============================================================================
# FICHIERS STATIQUES
# =============================================================================

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = []

dossier_static = BASE_DIR / "static"

if dossier_static.exists():
    STATICFILES_DIRS.append(dossier_static)


# Compression et cache des fichiers statiques avec WhiteNoise.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage."
            "CompressedManifestStaticFilesStorage"
        ),
    },
}


# =============================================================================
# FICHIERS MÉDIAS
# =============================================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# =============================================================================
# EMAIL
# =============================================================================

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}


# =============================================================================
# SÉCURITÉ HTTP EN PRODUCTION
# =============================================================================

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    SECURE_SSL_REDIRECT = True

    SESSION_COOKIE_SECURE = True

    CSRF_COOKIE_SECURE = True

    SECURE_HSTS_SECONDS = 31536000

    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

    SECURE_HSTS_PRELOAD = True

    SECURE_CONTENT_TYPE_NOSNIFF = True


# =============================================================================
# CLÉ PAR DÉFAUT DES MODÈLES
# =============================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
