"""ASGI config for Delta Feed."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "delta_feed.config.settings")
application = get_asgi_application()
