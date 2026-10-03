"""Django settings for the Unfold-based admin panel.

The admin runs as a *separate process* from the FastAPI student API, but both
point at the same SQLite file, so every change made here is immediately visible
to the student site.

Business tables are declared with ``managed = False`` in the models: Django must
never try to create or alter them, because FastAPI owns the schema.
"""
from __future__ import annotations

import os
from pathlib import Path

import django

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY", "django-admin-local-only-change-in-production"
)
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"

# The student API and this admin must share the browser origin so cookies and
# relative URLs keep working; ALLOWED_HOSTS is permissive for the same reason.
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    # must precede django.contrib.admin so Unfold's AdminSite is used
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "admin_site.users",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves /static itself. Without it the panel is unstyled
    # whenever DEBUG is off, because runserver only serves static files in
    # DEBUG mode — and it also removes the need for a separate static server
    # behind nginx in production.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "admin_site.urls"
WSGI_APPLICATION = "admin_site.wsgi.application"

# Unfold swaps Django's AdminSite for its own subclass. Using Unfold's AdminConfig
# (instead of django.contrib.admin's) makes `admin.site` that subclass from the
# start, so `@admin.register` below binds to the themed site and URLs resolve
# against it. Leaving the default in place yields an unthemed panel and 404s.
DEFAULT_ADMIN_SITE = "unfold.admin.UnfoldAdminSite"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "admin_site" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "admin_site.context.admin_context",
            ],
        },
    },
]

# Same physical file the FastAPI app uses.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "data" / "app.db",
        "OPTIONS": {
            # A busy SQLite file can block briefly; wait instead of crashing.
            "timeout": 20,
            "init_command": "PRAGMA journal_mode=WAL;",
            "transaction_mode": "IMMEDIATE",
        },
    }
}

AUTH_USER_MODEL = "users.AdminUser"
AUTH_PASSWORD_VALIDATORS = []
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "admin:index"
LOGOUT_REDIRECT_URL = "login"
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True

LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = False

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "data" / "django-static"
# Our admin_site/static directory is not an installed app's static folder, so
# point Django at it explicitly — otherwise admin_custom.css is never collected.
STATICFILES_DIRS = [BASE_DIR / "admin_site" / "static"]
# WhiteNoise serves from STATIC_ROOT, so collectstatic must run at least once.
# The manifest storage also gives long-lived, cache-busted static URLs.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------------------- Unfold
UNFOLD = {
    "SITE_TITLE": "OSH — Boshqaruv paneli",
    "SITE_HEADER": "admin_site/header.html",
    "SIDE_DEFAULT_CLOSED": False,
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "THEME": "dark",  # matches the student site
    # Unfold >=0.60 replaced the old "DASHBOARD" template key with
    # "DASHBOARD_CALLBACK", which receives (request, context) and may return
    # extra context. Using the stale key silently renders the default page.
    "DASHBOARD_CALLBACK": "admin_site.users.admin.dashboard_callback",
    # Unfold expects COLORS as {name: {weight: "#rrggbb"}}, and each colour
    # must be a flat hex string. Passing a flat {1: "#hex"} map makes
    # `_get_colors` call .items() on a str and every admin page returns 500.
    "COLORS": {
        "primary": {
            1: "#2f7cf6",   # brand — buttons, active nav
            2: "#4d8ef8",
            3: "#7fb0ff",
        },
        "secondary": {
            1: "#6b4bf0",   # accent
            2: "#8a70f5",
            3: "#b0a0fa",
        },
        "gray": {
            1: "#94a7c2",
            2: "#6b7f9e",
            3: "#3f4d63",
        },
        "surface": {
            1: "#16223a",   # cards
            2: "#1d2c48",
            3: "#0f1929",   # inputs
        },
        "border": {
            1: "#26374f",
            2: "#31445f",
            3: "#3d5372",
        },
    },
}
# Point the "back" button and logo at the student site.
UNFOLD["SITE_URL"] = os.getenv("STUDENT_SITE_URL", "http://127.0.0.1:8000/")