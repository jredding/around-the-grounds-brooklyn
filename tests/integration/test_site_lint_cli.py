"""Integration tests for the `site lint` CLI flow."""

from pathlib import Path
from typing import Any

import pytest

from around_the_grounds.config.writer import save_site_config
from around_the_grounds.main import main
from around_the_grounds.models import SiteConfig, Venue


def _venue(key: str = "union-hall") -> Venue:
    return Venue(
        key=key,
        name="Union Hall",
        url="https://unionhallny.com/calendar",
        source_type="html",
        parser_config={},
    )


def _site(key: str = "test-site", **overrides) -> SiteConfig:
    base = dict(
        key=key,
        name="Test Site",
        template="music",
        timezone="America/New_York",
        venues=[_venue()],
        target_repo="",
        generate_description=False,
    )
    base.update(overrides)
    return SiteConfig(**base)  # type: ignore[arg-type]


@pytest.fixture
def sites_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(
        "around_the_grounds.cli.lint_commands._sites_dir",
        lambda: tmp_path,
    )
    return tmp_path


class TestSiteLint:
    def test_clean_config_passes(self, sites_dir: Path, capsys: Any) -> None:
        save_site_config(_site(), sites_dir / "test-site.json")

        exit_code = main(["site", "lint"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "test-site.json: ok" in captured.out

    def test_single_site_filter(self, sites_dir: Path, capsys: Any) -> None:
        save_site_config(_site(), sites_dir / "test-site.json")

        exit_code = main(["site", "lint", "--site", "test-site"])

        assert exit_code == 0

    def test_filter_reports_missing_site(
        self, sites_dir: Path, capsys: Any
    ) -> None:
        exit_code = main(["site", "lint", "--site", "nope"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_empty_sites_dir_reports_error(
        self, sites_dir: Path, capsys: Any
    ) -> None:
        exit_code = main(["site", "lint"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "no site configs found" in captured.out

    def test_filename_key_mismatch_fails(
        self, sites_dir: Path, capsys: Any
    ) -> None:
        # Write a config whose key doesn't match the filename
        save_site_config(_site(key="wrong-key"), sites_dir / "test-site.json")

        exit_code = main(["site", "lint"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "does not match filename" in captured.out

    def test_invalid_timezone_fails(
        self, sites_dir: Path, capsys: Any
    ) -> None:
        save_site_config(
            _site(timezone="Not/A_Zone"), sites_dir / "test-site.json"
        )

        exit_code = main(["site", "lint"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Timezone" in captured.out

    def test_duplicate_venue_keys_fail(
        self, sites_dir: Path, capsys: Any
    ) -> None:
        save_site_config(
            _site(venues=[_venue(), _venue()]),
            sites_dir / "test-site.json",
        )

        exit_code = main(["site", "lint"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Duplicate venue key" in captured.out

    def test_invalid_json_reported(
        self, sites_dir: Path, capsys: Any
    ) -> None:
        (sites_dir / "broken.json").write_text("{ not-json")

        exit_code = main(["site", "lint"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "invalid JSON" in captured.out
