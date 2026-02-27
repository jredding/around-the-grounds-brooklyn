"""Generic WordPress REST API parser.

Triggered by source_type: "wordpress". Supports any site running
the WordPress REST API (wp-json/wp/v2/posts). Optionally filters
by category_id or resolves category_slug to an ID automatically.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

from ...models import Event, Venue
from ..base import BaseParser


class WordPressParser(BaseParser):
    """Generic parser for sites using the WordPress REST API."""

    def __init__(self, venue: Venue) -> None:
        super().__init__(venue)
        self.logger = logging.getLogger(self.__class__.__name__)

    async def parse(self, session: aiohttp.ClientSession) -> List[Event]:
        config = self.venue.parser_config or {}
        api_path = config.get("api_path", "/wp-json/wp/v2/posts")
        per_page = int(config.get("per_page", 20))
        category_id: Optional[int] = config.get("category_id")
        category_slug: Optional[str] = config.get("category_slug")

        base_url = self.venue.url.rstrip("/")

        # Resolve category_slug to ID if needed
        if category_slug and not category_id:
            category_id = await self._resolve_category_slug(
                session, base_url, category_slug
            )

        # Build query params
        params: Dict[str, Any] = {
            "per_page": per_page,
            "_embed": "true",
        }
        if category_id:
            params["categories"] = category_id

        url = f"{base_url}{api_path}"
        self.logger.debug(f"Fetching WordPress API: {url} params={params}")

        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    raise ValueError(
                        f"WordPress API returned HTTP {response.status}: {url}"
                    )
                posts = await response.json(content_type=None)
        except aiohttp.ClientError as e:
            raise ValueError(f"Network error fetching WordPress API {url}: {e}")

        if not isinstance(posts, list):
            self.logger.warning(
                f"Unexpected WordPress API response shape for {url}"
            )
            return []

        events = []
        for post in posts:
            event = self._parse_post(post)
            if event:
                events.append(event)

        self.logger.info(f"WordPressParser: {len(events)} events from {base_url}")
        return events

    def _parse_post(self, post: Dict[str, Any]) -> Optional[Event]:
        """Map a WP post dict to an Event."""
        try:
            title_raw = post.get("title", {}).get("rendered", "")
            title = re.sub(r"<[^>]+>", "", title_raw).strip()
            if not title:
                return None

            date_str = post.get("date", "")
            if not date_str:
                return None
            try:
                date = datetime.fromisoformat(date_str)
            except ValueError:
                self.logger.debug(f"Could not parse WP post date: {date_str!r}")
                return None

            excerpt_raw = post.get("excerpt", {}).get("rendered", "")
            description: Optional[str] = (
                re.sub(r"<[^>]+>", "", excerpt_raw).strip() or None
            )

            return Event(
                venue_key=self.venue.key,
                venue_name=self.venue.name,
                title=title,
                date=date,
                start_time=None,
                end_time=None,
                description=description,
                extraction_method="api",
            )
        except Exception as e:
            self.logger.debug(f"Error parsing WP post: {e}")
            return None

    async def _resolve_category_slug(
        self, session: aiohttp.ClientSession, base_url: str, slug: str
    ) -> Optional[int]:
        """Resolve a category slug to its numeric ID via the WP categories API."""
        url = f"{base_url}/wp-json/wp/v2/categories"
        params = {"slug": slug, "per_page": 1}
        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return None
                cats = await response.json(content_type=None)
                if cats and isinstance(cats, list):
                    return int(cats[0]["id"])
        except Exception as e:
            self.logger.warning(f"Failed to resolve category slug '{slug}': {e}")
        return None
