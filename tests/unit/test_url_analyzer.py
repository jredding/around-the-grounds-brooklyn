"""Unit tests for URL analysis helpers."""

import re
from unittest.mock import patch

import pytest
from aioresponses import aioresponses

from around_the_grounds.parsers.generic.html_selector import HtmlSelectorParser
from around_the_grounds.utils.url_analyzer import UrlAnalyzer, normalize_url


def test_normalize_url_adds_https_scheme() -> None:
    """Bare user input should be normalized to https URLs."""
    assert (
        normalize_url("unionhallny.com/calendar") == "https://unionhallny.com/calendar"
    )


@pytest.mark.asyncio
async def test_analyze_accepts_events_without_start_times() -> None:
    """Events missing start times should still produce a suggested config."""
    analyzer = UrlAnalyzer()
    html = """
    <html>
      <body>
        <div class="event-item">
          <h2 class="event-title">Open Mic Night</h2>
          <div class="event-date">April 10, 2026</div>
        </div>
      </body>
    </html>
    """

    with aioresponses() as mocked:
        mocked.get(
            "https://example.com/calendar",
            status=200,
            body=html,
            repeat=True,
        )
        mocked.get(
            re.compile(r"https://example.com/wp-json/.*"),
            status=404,
            repeat=True,
        )

        result = await analyzer.analyze("example.com/calendar")

    assert result.success is True
    assert result.venue_config is not None
    assert result.venue_config["source_type"] == "html"
    assert result.venue_config["parser_config"]["times_optional"] is True
    assert "Some events were found without start times." in result.warnings
    assert result.sample_events[0]["title"] == "Open Mic Night"


@pytest.mark.asyncio
async def test_analyze_uses_registry_driven_source_types() -> None:
    """Analyzer should derive attempted parser families from ParserRegistry."""
    analyzer = UrlAnalyzer()
    html = """
    <html>
      <body>
        <div class="event-item">
          <h2 class="event-title">Neighborhood Show</h2>
          <div class="event-date">April 11, 2026</div>
        </div>
      </body>
    </html>
    """

    with patch(
        "around_the_grounds.utils.url_analyzer.ParserRegistry.get_generic_parsers",
        return_value={"html": HtmlSelectorParser},
    ):
        with aioresponses() as mocked:
            mocked.get(
                "https://example.com/calendar",
                status=200,
                body=html,
                repeat=True,
            )

            result = await analyzer.analyze("https://example.com/calendar")

    assert result.success is True
    assert [attempt.strategy for attempt in result.attempts] == ["html"]


@pytest.mark.asyncio
async def test_analyze_returns_no_events_found_when_all_attempts_fail() -> None:
    """Failed analysis should stay in the simple no-events-found state."""
    analyzer = UrlAnalyzer()
    html = "<html><body><p>No events here.</p></body></html>"

    with aioresponses() as mocked:
        mocked.get(
            "https://example.com/calendar",
            status=200,
            body=html,
            repeat=True,
        )
        mocked.get(
            re.compile(r"https://example.com/wp-json/.*"),
            status=404,
            repeat=True,
        )

        result = await analyzer.analyze("https://example.com/calendar")

    assert result.success is False
    assert result.message == "no events found"
    assert result.venue_config is None


@pytest.mark.asyncio
async def test_analyze_adds_javascript_app_shell_hint() -> None:
    """Analyzer should surface a hint for JS-rendered app shells."""
    analyzer = UrlAnalyzer()
    html = """
    <html>
      <body>
        <noscript>You need to enable JavaScript to run this app.</noscript>
        <div id="root"></div>
        <script defer="defer" src="/static/js/main.123.js"></script>
      </body>
    </html>
    """

    with aioresponses() as mocked:
        mocked.get(
            "https://example.com/calendar",
            status=200,
            body=html,
            repeat=True,
        )
        mocked.get(
            re.compile(r"https://example.com/wp-json/.*"),
            status=404,
            repeat=True,
        )

        result = await analyzer.analyze("https://example.com/calendar")

    assert result.success is False
    assert (
        "Page appears to be a JavaScript-rendered app shell; event data may require browser or API-specific parsing."
        in result.warnings
    )


@pytest.mark.asyncio
async def test_analyze_does_not_reuse_saved_site_configs_for_new_domains() -> None:
    """Fresh domains should be probed with family heuristics, not unrelated saved configs."""
    analyzer = UrlAnalyzer()
    html = "<html><body><p>No events here.</p></body></html>"

    with aioresponses() as mocked:
        mocked.get(
            "https://example.com/calendar",
            status=200,
            body=html,
            repeat=True,
        )
        mocked.get(
            re.compile(r"https://example.com/wp-json/.*"),
            status=404,
            repeat=True,
        )

        result = await analyzer.analyze("https://example.com/calendar")

    html_attempt = next(
        attempt for attempt in result.attempts if attempt.strategy == "html"
    )
    assert html_attempt.parser_config in (
        {},
        {
            "event_container": '[itemtype*="Event"]',
            "title_selector": '[itemprop="name"]',
            "date_selector": '[itemprop="startDate"]',
            "date_attribute": "content",
        },
    )


@pytest.mark.asyncio
async def test_analyze_adds_afton_widget_hint() -> None:
    """Analyzer should surface a hint for embedded Afton ticket widgets."""
    analyzer = UrlAnalyzer()
    html = """
    <html>
      <body>
        <div id="afton-tickets-checkout"></div>
        <script src="https://cdn1.aftontickets.com/js/embedded-checkout/widget.js"></script>
      </body>
    </html>
    """

    with aioresponses() as mocked:
        mocked.get(
            "https://example.com/events",
            status=200,
            body=html,
            repeat=True,
        )
        mocked.get(
            re.compile(r"https://example.com/wp-json/.*"),
            status=404,
            repeat=True,
        )

        result = await analyzer.analyze("https://example.com/events")

    assert result.success is False
    assert (
        "Page appears to embed an Afton Tickets widget; event data may require widget or API-specific parsing."
        in result.warnings
    )


@pytest.mark.asyncio
async def test_analyze_detects_caveat_ajax_feed() -> None:
    """Caveat's exposed events API should produce a working ajax suggestion."""
    analyzer = UrlAnalyzer()
    html = """
    <html>
      <body>
        <noscript>You need to enable JavaScript to run this app.</noscript>
        <div id="root"></div>
        <script defer="defer" src="/static/js/main.123.js"></script>
      </body>
    </html>
    """
    payload = {
        "records": [
            {
                "fields": {
                    "Event": "Lectures on Tap",
                    "google_start_time": "2026-04-09T19:00:00-04:00",
                    "google_end_time": "2026-04-09T20:30:00-04:00",
                    "description": "A sharp lecture night.",
                }
            }
        ]
    }

    with aioresponses() as mocked:
        mocked.get("https://www.caveat.nyc/", status=200, body=html, repeat=True)
        mocked.get(
            "https://www.caveat.nyc/api/events/listings",
            status=200,
            payload=payload,
            repeat=True,
        )
        mocked.get(re.compile(r"https://www.caveat.nyc/wp-json/.*"), status=404, repeat=True)

        result = await analyzer.analyze("https://www.caveat.nyc/")

    assert result.success is True
    assert result.venue_config is not None
    assert result.venue_config["source_type"] == "ajax"
    assert result.venue_config["parser_config"]["api_url"] == "https://www.caveat.nyc/api/events/listings"
    assert result.sample_events[0]["title"] == "Lectures on Tap"


@pytest.mark.asyncio
async def test_analyze_detects_afton_widget_feed() -> None:
    """Afton widget pages should produce an ajax config backed by the widget API."""
    analyzer = UrlAnalyzer()
    html = """
    <html>
      <body>
        <div id="afton-tickets-checkout"></div>
        <script>
          _aft('init', { apiKey: 'abc123', debug: false });
        </script>
      </body>
    </html>
    """
    payload = {
        "data": [
            {
                "event_name": "Tiger Would",
                "start_time": "2026-04-09 19:00:00",
                "end_time": "2026-04-09 23:00:00",
            }
        ]
    }

    with aioresponses() as mocked:
        mocked.get("https://example.com/events", status=200, body=html, repeat=True)
        mocked.get(
            "https://aftontickets.com/api/get-events?key=abc123",
            status=200,
            payload=payload,
            repeat=True,
        )
        mocked.get(re.compile(r"https://example.com/wp-json/.*"), status=404, repeat=True)

        result = await analyzer.analyze("https://example.com/events")

    assert result.success is True
    assert result.venue_config is not None
    assert result.venue_config["source_type"] == "ajax"
    assert (
        result.venue_config["parser_config"]["api_url"]
        == "https://aftontickets.com/api/get-events?key=abc123"
    )
    assert result.sample_events[0]["title"] == "Tiger Would"
