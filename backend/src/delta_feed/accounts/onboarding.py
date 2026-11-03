"""First-session onboarding: topic selection and starter-pack sources (ADR 0005, step 1)."""
from collections.abc import Iterable

from django.db import transaction
from django.utils import timezone

from delta_feed.accounts.models import ReaderProfile, TopicSelection
from delta_feed.content.models import Source
from delta_feed.content.use_cases import ensure_source
from delta_feed.knowledge.models import Topic
from delta_feed.knowledge.starter_packs import StarterPack


class OnboardingError(ValueError):
    """The submitted choices do not match the offered starter packs."""


class OnboardingConflict(OnboardingError):
    """A chosen feed cannot be registered because the existing data disagrees."""


def is_onboarding_complete(user) -> bool:
    if not user.is_authenticated:
        return False
    return ReaderProfile.objects.filter(
        user=user, onboarding_completed_at__isnull=False
    ).exists()


def selected_topic_slugs(user) -> list[str]:
    return list(
        TopicSelection.objects.filter(user=user).order_by("topic__slug").values_list("topic__slug", flat=True)
    )


def _mark_complete(user) -> None:
    profile, _created = ReaderProfile.objects.get_or_create(user=user)
    if profile.onboarding_completed_at is None:
        profile.onboarding_completed_at = timezone.now()
        profile.save(update_fields=["onboarding_completed_at"])


def skip_onboarding(user) -> None:
    """Mark onboarding complete without changing topics, selections or sources."""
    _mark_complete(user)


def complete_onboarding(
    user, *, topic_slugs: Iterable[str], feed_urls: Iterable[str], packs: list[StarterPack]
) -> None:
    """Validate the choices against ``packs``, then apply them atomically.

    Idempotent: topics are upserted by slug, selections and source-topic links are
    get-or-create, and a feed that already has a source is attached, not re-registered
    or backfilled again.
    """
    offered = {pack.slug: pack for pack in packs}
    chosen_slugs = list(dict.fromkeys(topic_slugs))
    unknown_topics = [slug for slug in chosen_slugs if slug not in offered]
    if unknown_topics:
        raise OnboardingError(f"Unknown starter pack: {', '.join(unknown_topics)}")

    chosen_packs = [offered[slug] for slug in chosen_slugs]
    allowed_feeds = {feed.feed_url: (pack, feed) for pack in chosen_packs for feed in pack.feeds}
    chosen_urls = list(dict.fromkeys(feed_urls))
    unknown_feeds = [url for url in chosen_urls if url not in allowed_feeds]
    if unknown_feeds:
        raise OnboardingError("Feeds must come from the selected starter packs")

    with transaction.atomic():
        topics = {}
        for pack in chosen_packs:
            topic, _created = Topic.objects.update_or_create(
                slug=pack.slug, defaults={"title": pack.title, "description": pack.description}
            )
            TopicSelection.objects.get_or_create(user=user, topic=topic)
            topics[pack.slug] = topic
        for url in chosen_urls:
            pack, feed = allowed_feeds[url]
            if (
                not Source.objects.filter(rss_feed_url=url).exists()
                and Source.objects.filter(name=feed.name).exists()
            ):
                raise OnboardingConflict(f"A different source is already named '{feed.name}'")
            source, _created = ensure_source(
                name=feed.name, rss_feed_url=feed.feed_url, homepage_url=feed.homepage_url
            )
            topics[pack.slug].sources.add(source)
        _mark_complete(user)
