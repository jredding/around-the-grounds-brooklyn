"""Tests for site config writer helpers."""

from pathlib import Path

import pytest

from around_the_grounds.config.loader import load_site_from_path
from around_the_grounds.config.writer import (
    add_venues_to_site,
    create_site_config,
    remove_venue_from_site,
    save_site_config,
)
from around_the_grounds.models import SiteConfig, Venue


def _venue(key: str, url: str) -> Venue:
    return Venue(key=key, name=key, url=url, source_type="html", parser_config={})


def _site() -> SiteConfig:
    return SiteConfig(
        key="test-site",
        name="Test Site",
        template="music",
        timezone="America/New_York",
        venues=[_venue("union-hall", "https://unionhallny.com/calendar")],
        target_repo="https://github.com/example/test-site.git",
        generate_description=False,
    )


class TestSaveSiteConfig:
    def test_round_trip_persists_site(self, tmp_path: Path) -> None:
        path = tmp_path / "test-site.json"
        site = _site()

        written_path = save_site_config(site, path)
        loaded = load_site_from_path(written_path)

        assert written_path == path
        assert loaded.key == site.key
        assert loaded.name == site.name
        assert loaded.template == site.template
        assert loaded.timezone == site.timezone
        assert loaded.target_repo == site.target_repo
        assert loaded.generate_description is False
        assert [venue.key for venue in loaded.venues] == ["union-hall"]

    def test_atomic_write_leaves_no_temp_file(self, tmp_path: Path) -> None:
        path = tmp_path / "test-site.json"

        save_site_config(_site(), path)

        assert path.exists()
        assert list(tmp_path.glob("*.tmp")) == []


class TestCreateSiteConfig:
    def test_create_site_config_writes_file(self, tmp_path: Path) -> None:
        path = tmp_path / "fresh-site.json"

        site = create_site_config(
            key="fresh-site",
            name="Fresh Site",
            template="kids",
            timezone="America/New_York",
            venues=[_venue("lkbc", "https://littlekidbigcity.com")],
            target_repo="https://github.com/example/fresh-site.git",
            generate_description=False,
            path=path,
        )

        assert path.exists()
        assert site.key == "fresh-site"
        loaded = load_site_from_path(path)
        assert loaded.name == "Fresh Site"
        assert loaded.template == "kids"

    def test_create_site_config_raises_for_existing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "fresh-site.json"
        path.write_text("{}")

        with pytest.raises(FileExistsError):
            create_site_config(
                key="fresh-site",
                name="Fresh Site",
                template="kids",
                timezone="America/New_York",
                venues=[_venue("lkbc", "https://littlekidbigcity.com")],
                path=path,
            )


class TestAddVenuesToSite:
    def test_appends_new_venues_and_persists(self, tmp_path: Path) -> None:
        path = tmp_path / "test-site.json"
        save_site_config(_site(), path)

        updated = add_venues_to_site(
            "test-site",
            [_venue("littlefield", "https://littlefieldnyc.com")],
            tmp_path,
        )

        assert [venue.key for venue in updated.venues] == ["union-hall", "littlefield"]
        loaded = load_site_from_path(path)
        assert [venue.key for venue in loaded.venues] == ["union-hall", "littlefield"]

    def test_rejects_duplicate_existing_venue_keys(self, tmp_path: Path) -> None:
        save_site_config(_site(), tmp_path / "test-site.json")

        with pytest.raises(ValueError, match="union-hall"):
            add_venues_to_site(
                "test-site",
                [_venue("union-hall", "https://unionhallny.com/calendar")],
                tmp_path,
            )

    def test_rejects_duplicate_new_venue_keys(self, tmp_path: Path) -> None:
        save_site_config(_site(), tmp_path / "test-site.json")

        with pytest.raises(ValueError, match="littlefield"):
            add_venues_to_site(
                "test-site",
                [
                    _venue("littlefield", "https://littlefieldnyc.com"),
                    _venue("littlefield", "https://littlefieldnyc.com/events"),
                ],
                tmp_path,
            )


class TestRemoveVenueFromSite:
    def test_removes_venue_and_persists(self, tmp_path: Path) -> None:
        path = tmp_path / "test-site.json"
        site = _site()
        site.venues.append(_venue("littlefield", "https://littlefieldnyc.com"))
        save_site_config(site, path)

        updated = remove_venue_from_site("test-site", "littlefield", tmp_path)

        assert [venue.key for venue in updated.venues] == ["union-hall"]
        loaded = load_site_from_path(path)
        assert [venue.key for venue in loaded.venues] == ["union-hall"]

    def test_raises_for_missing_venue(self, tmp_path: Path) -> None:
        save_site_config(_site(), tmp_path / "test-site.json")

        with pytest.raises(KeyError, match="missing-venue"):
            remove_venue_from_site("test-site", "missing-venue", tmp_path)
