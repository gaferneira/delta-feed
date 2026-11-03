import logging

from django.conf import settings
from django.http import HttpRequest
from ninja import Router, Schema
from ninja.errors import HttpError

from delta_feed.accounts import onboarding
from delta_feed.knowledge.starter_packs import StarterPack, StarterPackError, load_packs

logger = logging.getLogger(__name__)

router = Router(tags=["onboarding"])


class StarterFeedOut(Schema):
    name: str
    feed_url: str
    homepage_url: str


class StarterPackOut(Schema):
    slug: str
    title: str
    description: str
    feeds: list[StarterFeedOut]


class OnboardingState(Schema):
    packs: list[StarterPackOut]
    selected_topics: list[str]


class OnboardingCompletion(Schema):
    topics: list[str] = []  # noqa: RUF012
    feed_urls: list[str] = []  # noqa: RUF012


def _packs() -> list[StarterPack]:
    try:
        return load_packs(settings.STARTER_PACKS_DIR)
    except StarterPackError as error:
        logger.error("Invalid starter packs: %s", error)
        raise HttpError(503, "Starter packs are unavailable") from error


@router.get("", response=OnboardingState)
def onboarding_state(request: HttpRequest):
    return {
        "packs": [
            {"slug": pack.slug, "title": pack.title, "description": pack.description,
             "feeds": [vars(feed) for feed in pack.feeds]}
            for pack in _packs()
        ],
        "selected_topics": onboarding.selected_topic_slugs(request.user),
    }


@router.post("/complete")
def complete(request: HttpRequest, payload: OnboardingCompletion):
    try:
        onboarding.complete_onboarding(
            request.user, topic_slugs=payload.topics, feed_urls=payload.feed_urls, packs=_packs()
        )
    except onboarding.OnboardingConflict as error:
        raise HttpError(409, str(error)) from error
    except onboarding.OnboardingError as error:
        raise HttpError(400, str(error)) from error
    return {"onboarding_complete": True}


@router.post("/skip")
def skip(request: HttpRequest):
    onboarding.skip_onboarding(request.user)
    return {"onboarding_complete": True}
