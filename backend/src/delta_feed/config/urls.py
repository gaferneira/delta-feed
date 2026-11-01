"""URL configuration for Delta Feed."""
from django.urls import path

from delta_feed.api import api

urlpatterns = [path("api/", api.urls)]
