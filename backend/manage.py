#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "delta_feed.config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
