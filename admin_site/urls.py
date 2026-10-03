"""URLs for the Unfold admin.

`/` sends staff straight to the panel and everyone else to the login page.
The student site lives on another port, so a "back" link is always available.
"""
from __future__ import annotations

import os

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView

# Importing the app's admin module installs our OSHAdminSite subclass, which is
# what makes the themed templates and the dashboard cards work. It has to happen
# before `admin.site.urls` is evaluated below.
import admin_site.users.admin  # noqa: F401

STUDENT_SITE = os.getenv("STUDENT_SITE_URL", "http://127.0.0.1:8000/")

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="login.html", extra_context={"student_site": STUDENT_SITE}),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(url="/admin/", permanent=False)),
]