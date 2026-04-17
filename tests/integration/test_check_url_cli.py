"""Integration tests for the check-url CLI flow."""

from typing import Any
from unittest.mock import AsyncMock, patch

from around_the_grounds.main import main
from around_the_grounds.utils.url_analyzer import AnalysisResult


class TestCheckUrlCLI:
    """Test CLI dispatch for check-url."""

    def test_main_check_url_human_output(self, capsys: Any) -> None:
        """Human-readable output should be routed through the check-url command."""
        result = AnalysisResult(
            url="https://unionhallny.com/calendar",
            success=True,
            venue_config={
                "key": "unionhall",
                "name": "Union Hall",
                "url": "https://unionhallny.com/calendar",
                "source_type": "html",
                "parser_config": {"event_container": ".event-item"},
            },
            confidence=0.62,
            sample_events=[{"date": "2026-04-10", "title": "Open Mic Night"}],
            warnings=["Some events were found without start times."],
            message="events found",
        )

        with patch(
            "around_the_grounds.cli.url_commands._run_check_url",
            new=AsyncMock(return_value=[result]),
        ):
            exit_code = main(["check-url", "unionhallny.com/calendar"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Suggested source type: html" in captured.out
        assert "Open Mic Night" in captured.out

    def test_main_check_url_json_output(self, capsys: Any) -> None:
        """JSON output should serialize check-url results without the legacy banner."""
        result = AnalysisResult(
            url="https://unionhallny.com/calendar",
            success=True,
            venue_config={
                "key": "unionhall",
                "name": "Union Hall",
                "url": "https://unionhallny.com/calendar",
                "source_type": "html",
                "parser_config": {"event_container": ".event-item"},
            },
            confidence=0.62,
            message="events found",
        )

        with patch(
            "around_the_grounds.cli.url_commands._run_check_url",
            new=AsyncMock(return_value=[result]),
        ):
            exit_code = main(["check-url", "unionhallny.com/calendar", "--json"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert '"source_type": "html"' in captured.out
        assert "Around the Grounds - Event Tracker" not in captured.out

    def test_main_check_url_invalid_parser_config_json(self, capsys: Any) -> None:
        """Invalid directed parser JSON should fail fast."""
        exit_code = main(
            [
                "check-url",
                "https://unionhallny.com/calendar",
                "--parser-config",
                "not-json",
            ]
        )

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "invalid --parser-config JSON" in captured.out
