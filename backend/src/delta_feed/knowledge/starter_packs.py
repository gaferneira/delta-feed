"""Starter packs: reviewed, versioned TOML files that pair a topic with suggested feeds."""
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from delta_feed.content.urls import safe_http_url

SCHEMA_VERSION = 1
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_PACK_KEYS = {"schema_version", "slug", "title", "description", "feeds"}
_FEED_KEYS = {"name", "feed_url", "homepage_url"}


class StarterPackError(ValueError):
    """A starter pack file is malformed; the message names the file and the problem."""


@dataclass(frozen=True)
class StarterFeed:
    name: str
    feed_url: str
    homepage_url: str


@dataclass(frozen=True)
class StarterPack:
    slug: str
    title: str
    description: str
    feeds: tuple[StarterFeed, ...]


def _text(table: dict, key: str, where: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StarterPackError(f"{where}: '{key}' must be a non-empty string")
    return value.strip()


def _https_url(table: dict, key: str, where: str) -> str:
    value = _text(table, key, where)
    if safe_http_url(value) != value or not value.startswith("https://"):
        raise StarterPackError(f"{where}: '{key}' must be an absolute https:// URL without credentials")
    return value


def _check_keys(table: dict, allowed: set[str], where: str) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise StarterPackError(f"{where}: unknown key(s) {', '.join(unknown)}")


def load_pack(path: Path) -> StarterPack:
    where = path.name
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise StarterPackError(f"{where}: invalid TOML ({error})") from error
    _check_keys(data, _PACK_KEYS, where)
    if data.get("schema_version") != SCHEMA_VERSION:
        raise StarterPackError(f"{where}: 'schema_version' must be {SCHEMA_VERSION}")
    slug = _text(data, "slug", where)
    if not _SLUG.fullmatch(slug) or len(slug) > 60:
        raise StarterPackError(f"{where}: 'slug' must be lowercase letters, digits and hyphens")
    raw_feeds = data.get("feeds")
    if not isinstance(raw_feeds, list) or not raw_feeds or not all(isinstance(f, dict) for f in raw_feeds):
        raise StarterPackError(f"{where}: 'feeds' must be a non-empty list of tables")
    feeds = []
    for index, raw in enumerate(raw_feeds, start=1):
        feed_where = f"{where} feed #{index}"
        _check_keys(raw, _FEED_KEYS, feed_where)
        name = _text(raw, "name", feed_where)
        if len(name) > 200:
            raise StarterPackError(f"{feed_where}: 'name' is longer than 200 characters")
        feeds.append(
            StarterFeed(
                name=name,
                feed_url=_https_url(raw, "feed_url", feed_where),
                homepage_url=_https_url(raw, "homepage_url", feed_where),
            )
        )
    for field in ("name", "feed_url"):
        values = [getattr(feed, field) for feed in feeds]
        if len(set(values)) != len(values):
            raise StarterPackError(f"{where}: duplicate feed {field}")
    return StarterPack(
        slug=slug,
        title=_text(data, "title", where),
        description=_text(data, "description", where),
        feeds=tuple(feeds),
    )


def load_packs(directory: Path) -> list[StarterPack]:
    """Load every ``*.toml`` pack in ``directory``, sorted by slug; any invalid file raises."""
    packs = [load_pack(path) for path in sorted(directory.glob("*.toml"))]
    for field, label in (("slug", "slug"), ("name", "feed name"), ("feed_url", "feed URL")):
        seen: set[str] = set()
        for pack in packs:
            for value in [pack.slug] if field == "slug" else [getattr(f, field) for f in pack.feeds]:
                if value in seen:
                    raise StarterPackError(f"Duplicate {label} across starter packs: {value}")
                seen.add(value)
    return sorted(packs, key=lambda pack: pack.slug)
