"""Tests for the generic WordPress REST API parser."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from around_the_grounds.models import Venue, Event
from around_the_grounds.parsers.generic.wordpress import WordPressParser


def _make_venue(
    key: str = "littlefield",
    url: str = "https://littlefieldnyc.com",
    parser_config: dict = None,
) -> Venue:
    return Venue(
        key=key,
        name="Littlefield",
        url=url,
        source_type="wordpress",
        parser_config=parser_config or {"api_path": "/wp-json/wp/v2/posts", "per_page": 5},
    )


def _make_post(
    title: str = "Jazz Night",
    date: str = "2025-07-04T20:00:00",
    excerpt: str = "<p>A great jazz night!</p>",
    post_id: int = 1,
) -> dict:
    return {
        "id": post_id,
        "title": {"rendered": title},
        "date": date,
        "excerpt": {"rendered": excerpt},
    }


class TestWordPressParser:
    """Tests for WordPressParser."""

    @pytest.mark.asyncio
    async def test_parse_returns_events(self) -> None:
        """Parser maps WP posts to Event objects correctly."""
        venue = _make_venue()
        parser = WordPressParser(venue)

        posts = [
            _make_post("Jazz Night", "2025-07-04T20:00:00", "<p>Live jazz.</p>"),
            _make_post("Rock Show", "2025-07-05T21:00:00", "<p>Rock and roll.</p>", post_id=2),
        ]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=posts)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        events = await parser.parse(mock_session)

        assert len(events) == 2
        assert events[0].title == "Jazz Night"
        assert events[0].venue_key == "littlefield"
        assert events[0].venue_name == "Littlefield"
        assert events[0].extraction_method == "api"
        assert events[0].date == datetime(2025, 7, 4, 20, 0, 0)
        assert events[0].description == "Live jazz."

        assert events[1].title == "Rock Show"
        assert events[1].date == datetime(2025, 7, 5, 21, 0, 0)

    @pytest.mark.asyncio
    async def test_parse_strips_html_from_title(self) -> None:
        """HTML in title.rendered is stripped."""
        venue = _make_venue()
        parser = WordPressParser(venue)

        posts = [_make_post("<strong>Jazz Night</strong>")]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=posts)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        events = await parser.parse(mock_session)

        assert len(events) == 1
        assert events[0].title == "Jazz Night"

    @pytest.mark.asyncio
    async def test_parse_strips_html_from_excerpt(self) -> None:
        """HTML tags in excerpt.rendered are stripped to plain text."""
        venue = _make_venue()
        parser = WordPressParser(venue)

        posts = [_make_post(excerpt="<p>Great <strong>event</strong>!</p>")]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=posts)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        events = await parser.parse(mock_session)

        assert len(events) == 1
        assert events[0].description == "Great event!"

    @pytest.mark.asyncio
    async def test_parse_skips_post_missing_title(self) -> None:
        """Posts with empty title are skipped."""
        venue = _make_venue()
        parser = WordPressParser(venue)

        posts = [_make_post(title="")]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=posts)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        events = await parser.parse(mock_session)

        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_parse_skips_post_missing_date(self) -> None:
        """Posts with empty date are skipped."""
        venue = _make_venue()
        parser = WordPressParser(venue)

        posts = [_make_post(date="")]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=posts)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        events = await parser.parse(mock_session)

        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_parse_skips_post_invalid_date(self) -> None:
        """Posts with unparseable date are skipped."""
        venue = _make_venue()
        parser = WordPressParser(venue)

        posts = [_make_post(date="not-a-date")]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=posts)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        events = await parser.parse(mock_session)

        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_parse_empty_list(self) -> None:
        """Empty API response returns no events."""
        venue = _make_venue()
        parser = WordPressParser(venue)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[])
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        events = await parser.parse(mock_session)

        assert events == []

    @pytest.mark.asyncio
    async def test_parse_http_error_raises(self) -> None:
        """Non-200 API response raises ValueError."""
        venue = _make_venue()
        parser = WordPressParser(venue)

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        with pytest.raises(ValueError, match="HTTP 404"):
            await parser.parse(mock_session)

    @pytest.mark.asyncio
    async def test_parse_uses_category_id_param(self) -> None:
        """Parser includes category filter param when category_id is configured."""
        venue = _make_venue(
            parser_config={
                "api_path": "/wp-json/wp/v2/posts",
                "per_page": 20,
                "category_id": 186,
            }
        )
        parser = WordPressParser(venue)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[_make_post()])
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        events = await parser.parse(mock_session)

        assert len(events) == 1
        # Verify the call was made with category param
        call_kwargs = mock_session.get.call_args
        params = call_kwargs[1].get("params") or call_kwargs[0][1] if len(call_kwargs[0]) > 1 else {}
        if not params and call_kwargs.kwargs:
            params = call_kwargs.kwargs.get("params", {})
        assert params.get("categories") == 186

    @pytest.mark.asyncio
    async def test_parse_start_end_time_none(self) -> None:
        """WP posts have no structured times — start_time and end_time are None."""
        venue = _make_venue()
        parser = WordPressParser(venue)

        posts = [_make_post()]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=posts)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        events = await parser.parse(mock_session)

        assert len(events) == 1
        assert events[0].start_time is None
        assert events[0].end_time is None

    @pytest.mark.asyncio
    async def test_parse_non_list_response_returns_empty(self) -> None:
        """Non-list API response (e.g. error object) returns empty list."""
        venue = _make_venue()
        parser = WordPressParser(venue)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"code": "rest_no_route"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        events = await parser.parse(mock_session)

        assert events == []
