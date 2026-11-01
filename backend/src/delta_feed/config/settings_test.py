"""Settings for automated tests: production settings plus the published dev key."""
import os

os.environ.setdefault("DJANGO_ALLOW_INSECURE_DEV_KEY", "true")

from delta_feed.config.settings import *
