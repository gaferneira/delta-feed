import re
from collections.abc import Mapping

from django.db.models import Q

from delta_feed.knowledge.models import Entity

_SAFE_IDENTIFIER_KIND = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def find_entities_by_strong_identifiers(
    identifiers: Mapping[str, str],
) -> list[Entity]:
    """Fetch rows with at least one exact strong-key match."""
    query = Q(pk__in=[])
    for kind, value in identifiers.items():
        if not value or not _SAFE_IDENTIFIER_KIND.fullmatch(kind):
            continue
        if kind == "canonical_url":
            query |= Q(canonical_url=value)
        elif kind == "slug":
            query |= Q(slug=value)
        else:
            query |= Q(**{f"identifiers__{kind}__exact": value})
    if not identifiers or not query.children:
        return []
    return list(Entity.objects.filter(query).distinct())


def strong_identifiers_for(entity: Entity) -> dict[str, str]:
    identifiers = {
        "canonical_url": entity.canonical_url,
        "slug": entity.slug,
    }
    identifiers.update(entity.identifiers)
    return {kind: value for kind, value in identifiers.items() if value}
