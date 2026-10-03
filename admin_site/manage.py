#!/usr/bin/env python
"""Entry point for the Unfold admin panel:  python admin_site/manage.py <cmd>"""
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "admin_site.settings")
    # Run from the project root so `admin_site` and `server` both import.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()