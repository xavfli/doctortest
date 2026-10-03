"""Template context shared by every admin page.

`student_site` powers the "back to the student site" button, so the URL lives in
one place instead of being hard-coded in each template.
"""
from __future__ import annotations

import os


def admin_context(request) -> dict:
    return {
        "student_site": os.getenv("STUDENT_SITE_URL", "http://127.0.0.1:8000/"),
        "osh_admin_title": "OSH — Boshqaruv paneli",
        # Turn on Unfold's built-in header back button and point it at the
        # student site. Without this the panel has no way out, which is the
        # exact problem the user reported.
        "show_back_button": True,
        "SITE_URL": os.getenv("STUDENT_SITE_URL", "http://127.0.0.1:8000/"),
        "site_url": os.getenv("STUDENT_SITE_URL", "http://127.0.0.1:8000/"),
    }