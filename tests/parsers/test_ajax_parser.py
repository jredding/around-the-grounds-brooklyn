"""Tests for the generic AJAX parser."""

from typing import Optional

import pytest
from aioresponses import aioresponses

from around_the_grounds.models import Venue
from around_the_grounds.parsers.generic.ajax import AjaxParser


def _venue(
    url: str = "https://example.com/events",
    parser_config: Optional[dict] = None,
) -> Venue:
    return Venue(
        key="example",
        name="Example Venue",
        url=url,
        source_type="ajax",
        parser_config=parser_config or {},
    )


class TestAjaxParserHelpers:
    """Focused helper tests for AjaxParser."""

    def test_extracts_afton_api_key_from_embedded_markup(self) -> None:
        """Afton embeds should expose a reusable API key."""
        html = """
        <div id="afton-tickets-checkout"></div>
        <script>
            _aft('init', { apiKey: 'abc123', debug: false });
        </script>
        """

        assert AjaxParser._extract_afton_api_key(html) == "abc123"

    def test_extracts_afton_api_key_returns_none_when_absent(self) -> None:
        """Pages without an Afton widget should return None."""
        assert AjaxParser._extract_afton_api_key("<html></html>") is None

    def test_known_endpoint_defaults_for_afton(self) -> None:
        """Afton event feeds should get built-in response defaults."""
        response_path, field_map = AjaxParser._known_endpoint_defaults(
            "https://aftontickets.com/api/get-events?key=abc123"
        )

        assert response_path == "data"
        assert field_map == {
            "title": "event_name",
            "date": "start_time",
            "start_time": "start_time",
            "end_time": "end_time",
        }

    def test_known_endpoint_defaults_unknown(self) -> None:
        """Unknown endpoints should return empty defaults."""
        response_path, field_map = AjaxParser._known_endpoint_defaults(
            "https://example.com/api/events"
        )

        assert response_path is None
        assert field_map == {}

    def test_nested_field_values_are_supported(self) -> None:
        """Nested field paths should resolve through dot notation."""
        item = {"fields": {"Event": "Lectures on Tap"}}

        assert AjaxParser._get_value(item, "fields.Event") == "Lectures on Tap"

    def test_flat_field_values_still_work(self) -> None:
        """Flat field paths must still read directly from the item."""
        item = {"name": "Open Mic"}

        assert AjaxParser._get_value(item, "name") == "Open Mic"

    def test_get_value_returns_default_when_missing(self) -> None:
        """Missing keys should return the default."""
        assert AjaxParser._get_value({}, "missing", "fallback") == "fallback"
        assert AjaxParser._get_value({}, "a.b.c", "fallback") == "fallback"


@pytest.mark.asyncio
async def test_discover_endpoint_finds_afton_widget(aiohttp_session) -> None:
    """Pages with Afton widgets should resolve to the widget event feed."""
    parser = AjaxParser(_venue(url="https://example.com/events"))
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

    with aioresponses() as mocked:
        mocked.get("https://example.com/events", status=200, body=html)
        endpoint = await parser._discover_endpoint(aiohttp_session)

    assert endpoint == "https://aftontickets.com/api/get-events?key=abc123"
