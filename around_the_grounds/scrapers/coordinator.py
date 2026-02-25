import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import aiohttp

from ..models import Venue, Event
from ..utils.timezone_utils import PACIFIC_TZ
from ..parsers import ParserRegistry


class ScrapingError:
    """Represents an error that occurred during scraping."""

    def __init__(
        self,
        venue: Venue,
        error_type: str,
        message: str,
        details: Optional[str] = None,
    ) -> None:
        self.venue = venue
        self.error_type = error_type
        self.message = message
        self.details = details
        self.timestamp = datetime.now()

    def __str__(self) -> str:
        return f"{self.error_type}: {self.message}"

    def to_user_message(self) -> str:
        """Create a user-facing summary of the scraping failure."""
        return f"Failed to fetch information for venue: {self.venue.name}"


class ScraperCoordinator:
    def __init__(
        self, max_concurrent: int = 5, timeout: int = 60, max_retries: int = 3
    ):
        self.max_concurrent = max_concurrent
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
        self.errors: List[ScrapingError] = []

    async def scrape_all(self, venues: List[Venue]) -> List[Event]:
        """
        Scrape all breweries concurrently and return aggregated events.
        Returns events and stores errors for later reporting.
        """
        self.errors = []  # Reset errors for this run

        connector = aiohttp.TCPConnector(limit=self.max_concurrent)
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=self.timeout,
            headers={"User-Agent": "Around-the-Grounds Food Truck Scraper"},
        ) as session:
            tasks = []
            for venue in venues:
                task = self._scrape_venue(session, venue)
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Aggregate results
            all_events: List[Event] = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # This shouldn't happen with our error handling, but just in case
                    error = ScrapingError(
                        venue=venues[i],
                        error_type="Unexpected Error",
                        message=f"Unexpected error: {str(result)}",
                        details=str(result),
                    )
                    self.errors.append(error)
                    self.logger.error(
                        f"Unexpected error scraping {venues[i].name}: {result}"
                    )
                    continue

                # Type narrowing: result is Tuple[List[Event], Optional[ScrapingError]]
                assert isinstance(
                    result, tuple
                ), "Result should be a tuple from _scrape_venue"
                events: List[Event]
                error_opt: Optional[ScrapingError]
                events, error_opt = result
                if error_opt:
                    self.errors.append(error_opt)
                all_events.extend(events)

        # Filter to next 7 days and sort by date
        return self._filter_and_sort_events(all_events)

    async def scrape_one(
        self, venue: Venue
    ) -> Tuple[List[Event], Optional[ScrapingError]]:
        """Scrape a single venue using an isolated HTTP session."""
        connector = aiohttp.TCPConnector(limit=1)
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=self.timeout,
            headers={"User-Agent": "Around-the-Grounds Food Truck Scraper"},
        ) as session:
            events, error = await self._scrape_venue(session, venue)

        filtered_events = self._filter_and_sort_events(events)
        self.errors = [error] if error else []
        return filtered_events, error

    async def _scrape_venue(
        self, session: aiohttp.ClientSession, venue: Venue
    ) -> Tuple[List[Event], Optional[ScrapingError]]:
        """Scrape a single venue with comprehensive error handling and retry logic."""
        try:
            parser_class = ParserRegistry.get_parser(venue.key)
            parser = parser_class(venue)
        except KeyError as e:
            error = ScrapingError(
                venue=venue,
                error_type="Configuration Error",
                message=f"Parser not found for venue key: {venue.key}",
                details=str(e),
            )
            self.logger.error(f"Configuration error for {venue.name}: {str(e)}")
            return [], error

        for attempt in range(self.max_retries):
            try:
                self.logger.info(
                    f"Scraping {venue.name} (attempt {attempt + 1}/{self.max_retries})..."
                )
                events = await parser.parse(session)
                self.logger.info(f"Found {len(events)} events for {venue.name}")
                return events, None

            except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
                error_msg = f"Connection timeout after {self.timeout.total}s"
                if attempt == self.max_retries - 1:
                    error = ScrapingError(
                        venue=venue,
                        error_type="Network Timeout",
                        message=error_msg,
                        details=f"Failed after {self.max_retries} attempts",
                    )
                    self.logger.error(f"Timeout scraping {venue.name}: {error_msg}")
                    return [], error
                wait_time = 2**attempt  # Exponential backoff
                self.logger.warning(
                    f"Timeout scraping {venue.name}, retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

            except aiohttp.ClientError as e:
                error_msg = f"Network error: {str(e)}"
                if attempt == self.max_retries - 1:
                    error = ScrapingError(
                        venue=venue,
                        error_type="Network Error",
                        message=error_msg,
                        details=f"Failed after {self.max_retries} attempts",
                    )
                    self.logger.error(
                        f"Network error scraping {venue.name}: {error_msg}"
                    )
                    return [], error
                wait_time = 2**attempt
                self.logger.warning(
                    f"Network error scraping {venue.name}, retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

            except ValueError as e:
                error = ScrapingError(
                    venue=venue,
                    error_type="Parser Error",
                    message=f"Parsing failed: {str(e)}",
                    details=str(e),
                )
                self.logger.error(f"Parser error for {venue.name}: {str(e)}")
                return [], error

            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                if attempt == self.max_retries - 1:
                    error = ScrapingError(
                        venue=venue,
                        error_type="Unexpected Error",
                        message=error_msg,
                        details=str(e),
                    )
                    self.logger.error(
                        f"Unknown error scraping {venue.name}: {error_msg}"
                    )
                    return [], error
                wait_time = 2**attempt
                self.logger.warning(
                    f"Unknown error scraping {venue.name}, retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

        return [], None

    def _filter_and_sort_events(
        self, events: List[Event]
    ) -> List[Event]:
        """
        Filter events to next 7 days and sort by date.
        Uses Seattle timezone to ensure events are filtered correctly regardless of server location.
        """
        # Use Pacific timezone consistently
        now = datetime.now(PACIFIC_TZ)
        one_week_later = now + timedelta(days=7)

        # Filter to next 7 days
        filtered_events = [
            event
            for event in events
            if now.date() <= event.datetime_start.date() <= one_week_later.date()
        ]

        # Sort by datetime_start
        filtered_events.sort(key=lambda x: x.datetime_start)

        return filtered_events

    def get_errors(self) -> List[ScrapingError]:
        """
        Get list of errors that occurred during scraping.
        """
        return self.errors

    def has_errors(self) -> bool:
        """
        Check if any errors occurred during scraping.
        """
        return len(self.errors) > 0
