"""Integration tests for the edit-site CLI flow."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from around_the_grounds.config.writer import save_site_config
from around_the_grounds.main import main
from around_the_grounds.models import SiteConfig, Venue
from around_the_grounds.utils.url_analyzer import AnalysisResult


def _seed_site(sites_dir: Path, venue_keys=("union-hall",)) -> Path:
    """Write a minimal site config for tests and return its path."""
    venues = [
        Venue(
            key=key,
            name=key.replace("-", " ").title(),
            url=f"https://{key}.example.com",
            source_type="html",
            parser_config={},
        )
        for key in venue_keys
    ]
    site = SiteConfig(
        key="test-site",
        name="Test Site",
        template="music",
        timezone="America/New_York",
        venues=venues,
        target_repo="",
        generate_description=False,
    )
    path = sites_dir / "test-site.json"
    save_site_config(site, path)
    return path


@pytest.fixture
def sites_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect edit-site / lint handlers to an isolated on-disk sites dir."""
    monkeypatch.setattr(
        "around_the_grounds.cli.site_commands._sites_dir",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "around_the_grounds.cli.lint_commands._sites_dir",
        lambda: tmp_path,
    )
    return tmp_path


class TestEditSiteShow:
    def test_show_prints_current_config(
        self, sites_dir: Path, capsys: Any
    ) -> None:
        _seed_site(sites_dir)

        exit_code = main(["edit-site", "test-site", "--show"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert '"key": "test-site"' in captured.out
        assert '"key": "union-hall"' in captured.out

    def test_show_reports_missing_site(self, sites_dir: Path, capsys: Any) -> None:
        exit_code = main(["edit-site", "nope", "--show"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "not found" in captured.out


class TestEditSiteAddUrl:
    def test_add_url_appends_venue(self, sites_dir: Path, capsys: Any) -> None:
        _seed_site(sites_dir)

        result = AnalysisResult(
            url="https://littlefieldnyc.com",
            success=True,
            venue_config={
                "key": "littlefield",
                "name": "Littlefield",
                "url": "https://littlefieldnyc.com",
                "source_type": "html",
                "parser_config": {"event_container": ".event-item"},
            },
            confidence=0.7,
            message="events found",
        )

        with patch(
            "around_the_grounds.cli.site_commands._analyze_urls",
            new=AsyncMock(return_value=[result]),
        ):
            exit_code = main(
                [
                    "edit-site",
                    "test-site",
                    "--add-url",
                    "https://littlefieldnyc.com",
                ]
            )

        assert exit_code == 0
        stored = json.loads((sites_dir / "test-site.json").read_text())
        assert [v["key"] for v in stored["venues"]] == ["union-hall", "littlefield"]

    def test_add_url_dry_run_does_not_write(
        self, sites_dir: Path, capsys: Any
    ) -> None:
        path = _seed_site(sites_dir)
        before = path.read_text()

        result = AnalysisResult(
            url="https://littlefieldnyc.com",
            success=True,
            venue_config={
                "key": "littlefield",
                "name": "Littlefield",
                "url": "https://littlefieldnyc.com",
                "source_type": "html",
                "parser_config": {},
            },
            confidence=0.7,
            message="events found",
        )

        with patch(
            "around_the_grounds.cli.site_commands._analyze_urls",
            new=AsyncMock(return_value=[result]),
        ):
            exit_code = main(
                [
                    "edit-site",
                    "test-site",
                    "--add-url",
                    "https://littlefieldnyc.com",
                    "--dry-run",
                ]
            )

        assert exit_code == 0
        assert path.read_text() == before
        captured = capsys.readouterr()
        assert '"key": "littlefield"' in captured.out

    def test_add_url_rejects_no_events(
        self, sites_dir: Path, capsys: Any
    ) -> None:
        path = _seed_site(sites_dir)
        before = path.read_text()

        result = AnalysisResult(
            url="https://offline.example.com",
            success=False,
            warnings=["Page appears to be a JavaScript app shell."],
            message="no events found",
        )

        with patch(
            "around_the_grounds.cli.site_commands._analyze_urls",
            new=AsyncMock(return_value=[result]),
        ):
            exit_code = main(
                [
                    "edit-site",
                    "test-site",
                    "--add-url",
                    "https://offline.example.com",
                ]
            )

        assert exit_code == 1
        assert path.read_text() == before
        captured = capsys.readouterr()
        assert "no events found" in captured.out

    def test_add_url_rejects_duplicate_venue_key(
        self, sites_dir: Path, capsys: Any
    ) -> None:
        _seed_site(sites_dir, venue_keys=("union-hall",))

        result = AnalysisResult(
            url="https://unionhallny.com/calendar",
            success=True,
            venue_config={
                "key": "union-hall",
                "name": "Union Hall",
                "url": "https://unionhallny.com/calendar",
                "source_type": "html",
                "parser_config": {},
            },
            confidence=0.7,
            message="events found",
        )

        with patch(
            "around_the_grounds.cli.site_commands._analyze_urls",
            new=AsyncMock(return_value=[result]),
        ):
            exit_code = main(
                [
                    "edit-site",
                    "test-site",
                    "--add-url",
                    "https://unionhallny.com/calendar",
                ]
            )

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "already exists" in captured.out


class TestEditSiteRemoveVenue:
    def test_remove_venue_persists(self, sites_dir: Path) -> None:
        path = _seed_site(sites_dir, venue_keys=("union-hall", "littlefield"))

        exit_code = main(
            ["edit-site", "test-site", "--remove-venue", "littlefield"]
        )

        assert exit_code == 0
        stored = json.loads(path.read_text())
        assert [v["key"] for v in stored["venues"]] == ["union-hall"]

    def test_remove_venue_dry_run(self, sites_dir: Path, capsys: Any) -> None:
        path = _seed_site(sites_dir, venue_keys=("union-hall", "littlefield"))
        before = path.read_text()

        exit_code = main(
            [
                "edit-site",
                "test-site",
                "--remove-venue",
                "littlefield",
                "--dry-run",
            ]
        )

        assert exit_code == 0
        assert path.read_text() == before
        captured = capsys.readouterr()
        # dry-run prints the config with the venue already gone
        assert '"key": "littlefield"' not in captured.out
        assert '"key": "union-hall"' in captured.out

    def test_remove_venue_missing_key(
        self, sites_dir: Path, capsys: Any
    ) -> None:
        _seed_site(sites_dir, venue_keys=("union-hall",))

        exit_code = main(
            ["edit-site", "test-site", "--remove-venue", "missing-venue"]
        )

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "not found" in captured.out


class TestEditSiteOperationGuard:
    def test_requires_exactly_one_operation(
        self, sites_dir: Path, capsys: Any
    ) -> None:
        _seed_site(sites_dir)

        exit_code = main(["edit-site", "test-site"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "exactly one of --show" in captured.out

    def test_rejects_two_operations(
        self, sites_dir: Path, capsys: Any
    ) -> None:
        _seed_site(sites_dir)

        exit_code = main(
            [
                "edit-site",
                "test-site",
                "--show",
                "--add-url",
                "https://example.com",
            ]
        )

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "exactly one of --show" in captured.out
