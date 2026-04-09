"""Tests for shared HTTP request defaults."""

import asyncio
from unittest.mock import AsyncMock, patch

from around_the_grounds.models import Venue
from around_the_grounds.scrapers.coordinator import ScraperCoordinator
from around_the_grounds.utils.http import default_request_headers
from around_the_grounds.utils.url_analyzer import AnalysisResult, UrlAnalyzer


class _FakeClientSession:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_default_request_headers_are_browser_like() -> None:
    """Shared request headers should mimic a normal browser request."""
    headers = default_request_headers()

    assert "Mozilla/5.0" in headers["User-Agent"]
    assert headers["Accept-Language"] == "en-US,en;q=0.9"


def test_url_analyzer_uses_default_request_headers() -> None:
    """Analyzer sessions should inherit shared browser-like headers."""
    captured = {}

    class FakeClientSession(_FakeClientSession):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured.update(kwargs)

    analyzer = UrlAnalyzer()
    result = AnalysisResult(url="https://example.com", success=False)

    with patch(
        "around_the_grounds.utils.url_analyzer.aiohttp.ClientSession",
        FakeClientSession,
    ), patch.object(
        UrlAnalyzer,
        "_analyze_with_session",
        new=AsyncMock(return_value=result),
    ):
        returned = asyncio.run(analyzer.analyze("https://example.com"))

    assert returned is result
    assert captured["headers"] == default_request_headers()


def test_scraper_coordinator_uses_default_request_headers() -> None:
    """Scraper sessions should inherit shared browser-like headers."""
    captured = {}

    class FakeClientSession(_FakeClientSession):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured.update(kwargs)

    venue = Venue(
        key="example",
        name="Example Venue",
        url="https://example.com/events",
        source_type="html",
        parser_config={},
    )
    coordinator = ScraperCoordinator()

    with patch(
        "around_the_grounds.scrapers.coordinator.aiohttp.ClientSession",
        FakeClientSession,
    ), patch.object(
        ScraperCoordinator,
        "_scrape_venue",
        new=AsyncMock(return_value=([], None)),
    ):
        asyncio.run(coordinator.scrape_one(venue))

    assert captured["headers"] == default_request_headers()
