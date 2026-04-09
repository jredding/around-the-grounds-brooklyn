"""Integration tests for the create-site CLI flow."""

from typing import Any
from unittest.mock import AsyncMock, patch

from around_the_grounds.main import main
from around_the_grounds.utils.url_analyzer import AnalysisResult


class TestCreateSiteCLI:
    """Test CLI dispatch for create-site."""

    def test_main_create_site_dry_run_outputs_config(self, capsys: Any) -> None:
        """Dry run should print the generated site config without writing."""
        results = [
            AnalysisResult(
                url="https://www.caveat.nyc/",
                success=True,
                venue_config={
                    "key": "caveat",
                    "name": "Caveat",
                    "url": "https://www.caveat.nyc/",
                    "source_type": "json-ld",
                    "parser_config": {},
                },
                confidence=0.95,
                message="events found",
            ),
            AnalysisResult(
                url="https://www.arlenesgrocerynyc.com/upcoming-events",
                success=True,
                venue_config={
                    "key": "arlenesgrocerynyc-upcoming-events",
                    "name": "Arlenesgrocerynyc Upcoming Events",
                    "url": "https://www.arlenesgrocerynyc.com/upcoming-events",
                    "source_type": "html",
                    "parser_config": {"event_container": ".event-item"},
                },
                confidence=0.61,
                message="events found",
            ),
        ]

        with patch(
            "around_the_grounds.cli.site_commands._analyze_urls",
            new=AsyncMock(return_value=results),
        ), patch(
            "around_the_grounds.cli.site_commands.validate_site_key_unique"
        ), patch(
            "around_the_grounds.cli.site_commands.validate_site_config"
        ):
            exit_code = main(
                [
                    "create-site",
                    "--key",
                    "lower-east-side-venues",
                    "--name",
                    "Lower East Side venues",
                    "--template",
                    "music",
                    "--timezone",
                    "America/New_York",
                    "--url",
                    "https://www.caveat.nyc/",
                    "--url",
                    "https://www.arlenesgrocerynyc.com/upcoming-events",
                    "--dry-run",
                ]
            )

        assert exit_code == 0
        captured = capsys.readouterr()
        assert '"key": "lower-east-side-venues"' in captured.out
        assert '"key": "caveat"' in captured.out
        assert '"key": "arlenesgrocerynyc-upcoming-events"' in captured.out

    def test_main_create_site_fails_when_url_has_no_events(self, capsys: Any) -> None:
        """Create-site should fail if any URL returns no events found."""
        results = [
            AnalysisResult(
                url="https://www.caveat.nyc/",
                success=True,
                venue_config={
                    "key": "caveat",
                    "name": "Caveat",
                    "url": "https://www.caveat.nyc/",
                    "source_type": "json-ld",
                    "parser_config": {},
                },
                confidence=0.95,
                message="events found",
            ),
            AnalysisResult(
                url="https://www.arlenesgrocerynyc.com/upcoming-events",
                success=False,
                warnings=["Page appears to embed an Afton Tickets widget."],
                message="no events found",
            ),
        ]

        with patch(
            "around_the_grounds.cli.site_commands._analyze_urls",
            new=AsyncMock(return_value=results),
        ), patch("around_the_grounds.cli.site_commands.validate_site_key_unique"):
            exit_code = main(
                [
                    "create-site",
                    "--key",
                    "lower-east-side-venues",
                    "--name",
                    "Lower East Side venues",
                    "--template",
                    "music",
                    "--timezone",
                    "America/New_York",
                    "--url",
                    "https://www.caveat.nyc/",
                    "--url",
                    "https://www.arlenesgrocerynyc.com/upcoming-events",
                ]
            )

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Some URLs returned no events found" in captured.out
        assert "hint: Page appears to embed an Afton Tickets widget." in captured.out

    def test_main_create_site_writes_config(self, capsys: Any) -> None:
        """Successful create-site should persist the generated config."""
        results = [
            AnalysisResult(
                url="https://www.caveat.nyc/",
                success=True,
                venue_config={
                    "key": "caveat",
                    "name": "Caveat",
                    "url": "https://www.caveat.nyc/",
                    "source_type": "json-ld",
                    "parser_config": {},
                },
                confidence=0.95,
                message="events found",
            )
        ]

        with patch(
            "around_the_grounds.cli.site_commands._analyze_urls",
            new=AsyncMock(return_value=results),
        ), patch(
            "around_the_grounds.cli.site_commands.validate_site_key_unique"
        ), patch(
            "around_the_grounds.cli.site_commands.validate_site_config"
        ), patch(
            "around_the_grounds.cli.site_commands.create_site_config"
        ) as mock_create:
            exit_code = main(
                [
                    "create-site",
                    "--key",
                    "lower-east-side-venues",
                    "--name",
                    "Lower East Side venues",
                    "--template",
                    "music",
                    "--timezone",
                    "America/New_York",
                    "--url",
                    "https://www.caveat.nyc/",
                ]
            )

        assert exit_code == 0
        mock_create.assert_called_once()
        captured = capsys.readouterr()
        assert (
            "Created site config at around_the_grounds/config/sites/lower-east-side-venues.json"
            in captured.out
        )
