"""Tests for the generic AJAX/JSON API parser.

Focus: transient vs. permanent failure classification. Transient HTTP/network
failures must propagate as aiohttp.ClientError so the ScraperCoordinator retries
them; permanent client errors must raise ValueError (non-retryable). Regression
test for Littlefield (Eventbrite) events vanishing whenever a single flaky
response was mislabeled as a permanent parser error.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from around_the_grounds.models import Venue
from around_the_grounds.parsers import ParserRegistry
from around_the_grounds.parsers.generic.ajax import AjaxParser
from around_the_grounds.scrapers.coordinator import ScraperCoordinator


def _make_venue(parser_config: dict = None) -> Venue:
    return Venue(
        key="littlefield",
        name="Littlefield",
        url="https://littlefieldnyc.com",
        source_type="ajax",
        parser_config=parser_config
        or {
            "api_url": (
                "https://littlefieldnyc.com/wp-json/"
                "widget-for-eventbrite-api/v1/eb_events"
            ),
            "params": {"limit": 50},
            "field_map": {
                "title": "title",
                "date": "start",
                "start_time": "start",
                "end_time": "end",
                "description": "excerpt",
            },
        },
    )


def _make_response(status: int, payload: object = None) -> AsyncMock:
    """Build a mock aiohttp response usable as an async context manager."""
    mock_response = AsyncMock()
    mock_response.status = status
    mock_response.json = AsyncMock(return_value=payload if payload is not None else [])
    mock_response.request_info = MagicMock()
    mock_response.history = ()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    return mock_response


def _session_returning(*responses: AsyncMock) -> MagicMock:
    """Mock session whose .get returns each response in turn on successive calls."""
    mock_session = MagicMock()
    mock_session.get = MagicMock(side_effect=list(responses))
    return mock_session


def _sample_events() -> list:
    return [
        {
            "title": "SLOW JAMS NYC",
            "start": "2026-06-20T20:00:00",
            "end": "2026-06-20T23:00:00",
        },
        {
            "title": "REGGAE REWIND",
            "start": "2026-06-21T21:00:00",
            "end": "2026-06-22T01:00:00",
        },
    ]


class TestAjaxParserStatusClassification:
    @pytest.mark.asyncio
    async def test_parse_returns_events(self) -> None:
        """Happy path: 200 response is mapped to Event objects."""
        parser = AjaxParser(_make_venue())
        session = _session_returning(_make_response(200, _sample_events()))

        events = await parser.parse(session)

        assert len(events) == 2
        assert events[0].title == "SLOW JAMS NYC"
        assert events[0].venue_name == "Littlefield"
        assert events[0].extraction_method == "api"
        assert events[0].date == datetime(2026, 6, 20, 20, 0, 0)

    @pytest.mark.asyncio
    async def test_permanent_404_raises_value_error(self) -> None:
        """A permanent client error (404) raises ValueError (non-retryable)."""
        parser = AjaxParser(_make_venue())
        session = _session_returning(_make_response(404))

        with pytest.raises(ValueError, match="HTTP 404"):
            await parser.parse(session)

    @pytest.mark.parametrize("status", [408, 425, 429, 500, 502, 503, 504])
    @pytest.mark.asyncio
    async def test_transient_status_raises_client_error(self, status: int) -> None:
        """Transient statuses raise aiohttp.ClientError so the coordinator retries.

        Critically, ClientError is NOT a subclass of ValueError, so the
        coordinator's retry/backoff path engages instead of giving up.
        """
        parser = AjaxParser(_make_venue())
        session = _session_returning(_make_response(status))

        with pytest.raises(aiohttp.ClientError):
            await parser.parse(session)

    @pytest.mark.asyncio
    async def test_network_error_propagates_unwrapped(self) -> None:
        """A network-level ClientError propagates as ClientError, not ValueError."""
        parser = AjaxParser(_make_venue())
        session = MagicMock()
        session.get = MagicMock(side_effect=aiohttp.ClientConnectionError("boom"))

        with pytest.raises(aiohttp.ClientError):
            await parser.parse(session)


class TestAjaxParserCoordinatorRetry:
    """End-to-end: a transient failure is retried and recovers (the actual fix)."""

    @pytest.mark.asyncio
    async def test_transient_failure_then_success_recovers(self) -> None:
        """503 on first attempt, 200 on retry → events returned, no error recorded."""
        coordinator = ScraperCoordinator(max_concurrent=1, timeout=5, max_retries=3)
        coordinator._timezone = "America/New_York"
        venue = _make_venue()

        # Real AjaxParser via the registry, fed a session that fails once.
        session = _session_returning(
            _make_response(503),
            _make_response(200, _sample_events()),
        )

        with patch(
            "around_the_grounds.scrapers.coordinator.asyncio.sleep",
            new=AsyncMock(),
        ):
            events, error = await coordinator._scrape_venue(session, venue)

        assert error is None
        assert len(events) == 2
        assert session.get.call_count == 2

    @pytest.mark.asyncio
    async def test_registry_resolves_ajax_parser(self) -> None:
        """Sanity: source_type 'ajax' resolves to AjaxParser."""
        parser_class = ParserRegistry.get_parser(_make_venue())
        assert parser_class is AjaxParser
