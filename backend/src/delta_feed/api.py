from django.views.decorators.csrf import csrf_protect
from ninja import NinjaAPI
from ninja.security import SessionAuth

from delta_feed.accounts.api import router as accounts_router
from delta_feed.accounts.onboarding_api import router as onboarding_router
from delta_feed.content.api import router as content_router
from delta_feed.content.sources_api import router as sources_router
from delta_feed.guides.api import router as guides_router
from delta_feed.knowledge.api import router as knowledge_router
from delta_feed.reader.api import router as reader_router

api = NinjaAPI(auth=SessionAuth(), title="Delta Feed API", version="1.0.0")
api.add_decorator(csrf_protect, mode="view")
api.add_router("accounts/", accounts_router)
api.add_router("onboarding", onboarding_router)
api.add_router("content/", content_router)
api.add_router("content/", sources_router)
api.add_router("reader/", reader_router)
api.add_router("guides/", guides_router)
api.add_router("knowledge/", knowledge_router)
