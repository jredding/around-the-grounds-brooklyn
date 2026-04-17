"""Shared HTTP request helpers."""

from typing import Dict


def default_request_headers() -> Dict[str, str]:
    """Return browser-like headers for fetching public event pages.

    Venue pages behind bot filters commonly reject bare or scraper-like
    clients with 403. Sharing one realistic header set across the
    scraper and the URL analyzer keeps analyzer suggestions consistent
    with what the production scraper later sees.
    """
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/135.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
