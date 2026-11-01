"""WSGI config for Delta Feed."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "delta_feed.config.settings")
application = get_wsgi_application()
