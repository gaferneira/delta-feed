from pathlib import Path

import pytest
from django.conf import settings

from delta_feed.knowledge.starter_packs import StarterPackError, load_pack, load_packs

VALID = """\
schema_version = 1
slug = "demo"
title = "Demo"
description = "A demo pack."

[[feeds]]
name = "Demo feed"
feed_url = "https://demo.example/feed.xml"
homepage_url = "https://demo.example/"
"""


def write(tmp_path: Path, text: str, name: str = "demo.toml") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_a_valid_pack(tmp_path):
    pack = load_pack(write(tmp_path, VALID))
    assert (pack.slug, pack.title) == ("demo", "Demo")
    assert [(f.name, f.feed_url) for f in pack.feeds] == [("Demo feed", "https://demo.example/feed.xml")]


@pytest.mark.parametrize(
    ("old", "new", "fragment"),
    [
        ('title = "Demo"\n', 'title = "Demo"\nextra = 1\n', "unknown key"),
        ('name = "Demo feed"\n', 'name = "Demo feed"\nrss = "x"\n', "unknown key"),
        ('title = "Demo"\n', "", "'title'"),
        ('description = "A demo pack."\n', 'description = ""\n', "'description'"),
        ('homepage_url = "https://demo.example/"\n', "", "'homepage_url'"),
        ("schema_version = 1", "schema_version = 2", "schema_version"),
        ('slug = "demo"', 'slug = "Not A Slug"', "'slug'"),
        ("https://demo.example/feed.xml", "http://demo.example/feed.xml", "https://"),
        ("https://demo.example/feed.xml", "https://user:pw@demo.example/feed.xml", "https://"),
        ("https://demo.example/feed.xml", "ftp://demo.example/feed.xml", "https://"),
        ("https://demo.example/\"", "not a url\"", "'homepage_url'"),
        ("[[feeds]]", "[feeds]", "'feeds'"),
    ],
)
def test_rejects_invalid_pack(tmp_path, old, new, fragment):
    with pytest.raises(StarterPackError, match=fragment) as error:
        load_pack(write(tmp_path, VALID.replace(old, new)))
    assert "demo.toml" in str(error.value)


def test_rejects_pack_without_feeds_and_invalid_toml(tmp_path):
    header = VALID.split("[[feeds]]")[0]
    with pytest.raises(StarterPackError, match="'feeds'"):
        load_pack(write(tmp_path, header))
    with pytest.raises(StarterPackError, match="invalid TOML"):
        load_pack(write(tmp_path, "slug = ", "broken.toml"))


def test_rejects_duplicate_feeds_within_a_pack(tmp_path):
    feed = VALID.split("[[feeds]]")[1]
    with pytest.raises(StarterPackError, match="duplicate feed feed_url"):
        load_pack(write(tmp_path, VALID + "\n[[feeds]]" + feed.replace("Demo feed", "Other")))


def test_rejects_duplicate_slugs_names_and_urls_across_packs(tmp_path):
    write(tmp_path, VALID, "a.toml")
    write(tmp_path, VALID, "b.toml")
    with pytest.raises(StarterPackError, match="Duplicate slug"):
        load_packs(tmp_path)
    write(tmp_path, VALID.replace('slug = "demo"', 'slug = "other"'), "b.toml")
    with pytest.raises(StarterPackError, match="Duplicate feed name"):
        load_packs(tmp_path)
    other = VALID.replace('slug = "demo"', 'slug = "other"').replace("Demo feed", "Other feed")
    write(tmp_path, other, "b.toml")
    with pytest.raises(StarterPackError, match="Duplicate feed URL"):
        load_packs(tmp_path)


def test_missing_directory_yields_no_packs(tmp_path):
    assert load_packs(tmp_path / "missing") == []


def test_shipped_packs_are_valid():
    packs = load_packs(settings.STARTER_PACKS_DIR)
    assert {pack.slug for pack in packs} >= {"home-automation", "ai", "developer-tooling", "mobile"}
