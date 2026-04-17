"""Tests for site config validation helpers."""

from pathlib import Path

import pytest

from around_the_grounds.config.validator import (
    SiteConfigValidationError,
    validate_site_config,
    validate_site_key_unique,
)
from around_the_grounds.models import SiteConfig, Venue


def _site() -> SiteConfig:
    return SiteConfig(
        key="test-site",
        name="Test Site",
        template="music",
        timezone="America/New_York",
        venues=[
            Venue(
                key="union-hall",
                name="Union Hall",
                url="https://unionhallny.com/calendar",
                source_type="html",
                parser_config={},
            )
        ],
        target_repo="https://github.com/example/test-site.git",
        generate_description=False,
    )


class TestValidateSiteConfig:
    def test_accepts_valid_site_config(self) -> None:
        validate_site_config(_site())

    def test_rejects_missing_template(self) -> None:
        site = _site()
        site.template = "missing-template"

        with pytest.raises(SiteConfigValidationError, match="Template"):
            validate_site_config(site)

    def test_rejects_invalid_timezone(self) -> None:
        site = _site()
        site.timezone = "Mars/Olympus"

        with pytest.raises(SiteConfigValidationError, match="Timezone"):
            validate_site_config(site)

    def test_rejects_duplicate_venue_keys(self) -> None:
        site = _site()
        site.venues.append(
            Venue(
                key="union-hall",
                name="Duplicate Union Hall",
                url="https://example.com/events",
                source_type="html",
                parser_config={},
            )
        )

        with pytest.raises(SiteConfigValidationError, match="Duplicate venue key"):
            validate_site_config(site)

    def test_rejects_invalid_target_repo(self) -> None:
        site = _site()
        site.target_repo = "git@github.com:example/test-site.git"

        with pytest.raises(SiteConfigValidationError, match="Target repo"):
            validate_site_config(site)

    def test_rejects_unknown_parser_resolution(self) -> None:
        site = _site()
        site.venues = [
            Venue(
                key="mystery-venue",
                name="Mystery Venue",
                url="https://example.com/events",
                source_type="rss",
                parser_config={},
            )
        ]

        with pytest.raises(SiteConfigValidationError, match="No parser for venue"):
            validate_site_config(site)

    def test_rejects_invalid_url(self) -> None:
        site = _site()
        site.venues[0].url = "ftp://example.com/events"

        with pytest.raises(SiteConfigValidationError, match="invalid URL"):
            validate_site_config(site)


class TestValidateSiteKeyUnique:
    def test_raises_when_site_key_exists(self, tmp_path: Path) -> None:
        (tmp_path / "test-site.json").write_text("{}")

        with pytest.raises(SiteConfigValidationError, match="already exists"):
            validate_site_key_unique("test-site", tmp_path)

    def test_allows_unique_site_key(self, tmp_path: Path) -> None:
        validate_site_key_unique("new-site", tmp_path)
