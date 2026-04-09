"""Tests for the generic AJAX parser."""

from typing import Optional

import pytest

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

    def test_nested_field_values_are_supported(self) -> None:
        """Nested field paths should resolve through dot notation."""
        parser = AjaxParser(_venue())
        item = {"fields": {"Event": "Lectures on Tap"}}

        assert parser._get_value(item, "fields.Event") == "Lectures on Tap"


@pytest.mark.asyncio
async def test_discover_endpoint_finds_afton_widget(aiohttp_session) -> None:
    """Pages with Afton widgets should resolve to the widget event feed."""
    from aioresponses import aioresponses

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
