"""
Django settings for circuitprojet project.
Compatible local Windows + production serveur.
"""

from pathlib import Path
import os
from dotenv import load_dotenv


# ============================================================
# BASE
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_str(name, default=""):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def env_int(name, default=0):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def env_list(name, default=None):
    """
    Convertit une variable .env séparée par virgules en liste Python.
    Exemple :
    ALLOWED_HOSTS=localhost,127.0.0.1,pulsion-inscription.com
    """
    if default is None:
        default = []
    value = os.environ.get(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


DJANGO_ENV = env_str("DJANGO_ENV", "local").lower()
IS_PRODUCTION = DJANGO_ENV in {"production", "prod"}

SECRET_KEY = env_str(
    "SECRET_KEY",
    "django-insecure-local-dev-key-change-me"
)

DEBUG = env_bool("DJANGO_DEBUG", default=not IS_PRODUCTION)

if IS_PRODUCTION and DEBUG:
    raise RuntimeError("DJANGO_DEBUG=True est interdit en production.")

if IS_PRODUCTION and SECRET_KEY == "django-insecure-local-dev-key-change-me":
    raise RuntimeError("SECRET_KEY doit être défini dans .env en production.")


# ============================================================
# HOSTS / CSRF
# ============================================================

ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    default=[
        "localhost",
        "127.0.0.1",
        "84.247.132.41",
        "pulsion-inscription.com",
        "www.pulsion-inscription.com",
    ],
)

CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8001",
        "http://127.0.0.1:8001",
        "https://pulsion-inscription.com",
        "https://www.pulsion-inscription.com",
    ],
)


# ============================================================
# APPLICATIONS
# ============================================================

INSTALLED_APPS = [
    "modeltranslation",

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sitemaps",

    "circuitMoto.apps.CircuitMotoConfig",
    "formtools",
]

MODELTRANSLATION_DEFAULT_LANGUAGE = "fr"
MODELTRANSLATION_ENABLE_FALLBACKS = True
MODELTRANSLATION_FALLBACK_LANGUAGES = ("fr",)


# ============================================================
# MIDDLEWARE
# ============================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "circuitMoto.middleware.NoCacheHtmlMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "circuitMoto.middleware.ForcePasswordChangeMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "circuitprojet.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "circuitMoto.context_processors.site_prefs",
            ],
        },
    },
]

WSGI_APPLICATION = "circuitprojet.wsgi.application"


# ============================================================
# DATABASE
# ============================================================

DB_ENGINE = env_str("DB_ENGINE", "sqlite").lower()

if DB_ENGINE in {"postgres", "postgresql"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env_str("DB_NAME", "circuit"),
            "USER": env_str("DB_USER", "postgres"),
            "PASSWORD": env_str("DB_PASSWORD", ""),
            "HOST": env_str("DB_HOST", "localhost"),
            "PORT": env_str("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / env_str("SQLITE_NAME", "db.sqlite3"),
        }
    }


# ============================================================
# PASSWORDS
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
    {
        "NAME": "circuitMoto.validators.PreventPasswordReuseValidator",
    },
]


# ============================================================
# INTERNATIONALISATION
# ============================================================

LANGUAGE_CODE = "fr"
TIME_ZONE = env_str("TIME_ZONE", "UTC")

USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("fr", "Français"),
    ("en", "English"),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

LANGUAGE_COOKIE_NAME = "django_language"
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365
LANGUAGE_COOKIE_SAMESITE = "Lax"


# ============================================================
# STATIC / MEDIA
# ============================================================

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STATIC_VERSION = env_str("STATIC_VERSION", "")
STATIC_VERSION_QUERY = env_bool("STATIC_VERSION_QUERY", True)
STATIC_VERSION_PARAM = env_str("STATIC_VERSION_PARAM", "v")
STATIC_VERSION_EXTENSIONS = (
    ".css", ".js", ".mjs", ".json", ".map",
    ".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico",
    ".woff", ".woff2",
)

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

DATA_UPLOAD_MAX_MEMORY_SIZE = env_int("DATA_UPLOAD_MAX_MEMORY_SIZE", 10 * 1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = env_int("FILE_UPLOAD_MAX_MEMORY_SIZE", 2 * 1024 * 1024)

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}


# ============================================================
# SECURITY
# ============================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", IS_PRODUCTION)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", IS_PRODUCTION)

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

if IS_PRODUCTION:
    SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
    SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", True)
else:
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False


# ============================================================
# AUTH / REDIRECTIONS
# ============================================================

LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

CSRF_FAILURE_VIEW = "circuitMoto.errors.csrf_failure"


# ============================================================
# EMAIL
# ============================================================

EMAIL_BACKEND = env_str(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
)

EMAIL_HOST = env_str(
    "EMAIL_HOST",
    "smtp-relay.brevo.com" if IS_PRODUCTION else "smtp.gmail.com",
)

EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)

EMAIL_HOST_USER = (
    env_str("EMAIL_HOST_USER")
    or env_str("BREVO_SMTP_LOGIN")
)

EMAIL_HOST_PASSWORD = (
    env_str("EMAIL_HOST_PASSWORD")
    or env_str("BREVO_SMTP_KEY")
    or env_str("EMAIL_APP_PASSWORD")
)

DEFAULT_FROM_EMAIL = env_str(
    "DEFAULT_FROM_EMAIL",
    "Pulsion Horizon <info@pulsion-horizon.com>" if IS_PRODUCTION else "Pulsion Horizon <bayesalioudiawtech@gmail.com>",
)

SERVER_EMAIL = env_str("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

SITE_URL = env_str(
    "SITE_URL",
    "https://pulsion-inscription.com" if IS_PRODUCTION else "http://127.0.0.1:8000",
)

NOTIFY_ADMIN_EMAIL = env_str(
    "NOTIFY_ADMIN_EMAIL",
    "info@pulsion-horizon.com" if IS_PRODUCTION else "bayesalioudiawtech@gmail.com",
)

PASSWORD_RESET_TIMEOUT = env_int("PASSWORD_RESET_TIMEOUT", 60 * 60 * 2)
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 15)


# ============================================================
# API / EXTERNES
# ============================================================

GOOGLE_MAPS_API_KEY = env_str("GOOGLE_MAPS_API_KEY", "").strip()


# ============================================================
# NEWSLETTER / EMAILING DE MASSE
# ============================================================

NEWSLETTER_ENABLED = env_bool("NEWSLETTER_ENABLED", True)
NEWSLETTER_MAX_RECIPIENTS_PER_SEND = env_int("NEWSLETTER_MAX_RECIPIENTS_PER_SEND", 1500)
NEWSLETTER_BATCH_SIZE = env_int("NEWSLETTER_BATCH_SIZE", 50)
NEWSLETTER_SLEEP_SECONDS = env_int("NEWSLETTER_SLEEP_SECONDS", 1)
NEWSLETTER_MAX_ATTACHMENT_BYTES = env_int("NEWSLETTER_MAX_ATTACHMENT_BYTES", 25 * 1024 * 1024)
NEWSLETTER_HIDE_OLD_EMAILING = env_bool("NEWSLETTER_HIDE_OLD_EMAILING", True)

EMAILS_PAUSE_TOUS_UTILISATEURS = env_bool("EMAILS_PAUSE_TOUS_UTILISATEURS", False)
EMAILS_PAUSE_PILOTE = env_bool("EMAILS_PAUSE_PILOTE", False)
EMAILS_PAUSE_PASSAGER = env_bool("EMAILS_PAUSE_PASSAGER", False)