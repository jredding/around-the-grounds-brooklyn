"""Validation helpers for site configuration."""

from pathlib import Path
from typing import List, Optional, Set
from urllib.parse import urlparse

try:
    from zoneinfo import ZoneInfo  # type: ignore
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore

from ..models import SiteConfig, Venue
from ..parsers.registry import ParserRegistry


class SiteConfigValidationError(ValueError):
    """Raised when a site config fails validation."""


def validate_site_config(site: SiteConfig) -> None:
    """Validate a SiteConfig for basic correctness."""
    if not site.key.strip():
        raise SiteConfigValidationError("Site key cannot be empty.")
    if not site.name.strip():
        raise SiteConfigValidationError("Site name cannot be empty.")

    _validate_template(site.template)
    _validate_timezone(site.timezone)
    _validate_target_repo(site.target_repo)
    _validate_venues(site.venues)


def validate_site_key_unique(site_key: str, sites_dir: Optional[Path] = None) -> None:
    """Ensure a site key is not already in use."""
    directory = sites_dir or Path(__file__).parent / "sites"
    config_path = directory / f"{site_key}.json"
    if config_path.exists():
        raise SiteConfigValidationError(f"Site key '{site_key}' already exists.")


def _validate_template(template_name: str) -> None:
    """Ensure a template directory exists."""
    template_dir = _resolve_template_dir(template_name)
    if template_dir is None or not template_dir.is_dir():
        raise SiteConfigValidationError(f"Template '{template_name}' was not found.")


def _resolve_template_dir(template_name: str) -> Optional[Path]:
    """Locate a template directory using the same fallbacks as runtime flows."""
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [
        repo_root / "public_templates" / template_name,
        Path.cwd() / "public_templates" / template_name,
    ]

    if template_name == "food-trucks":
        candidates.extend(
            [
                repo_root / "public_template",
                Path.cwd() / "public_template",
            ]
        )

    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def _validate_timezone(timezone_name: str) -> None:
    """Ensure a timezone string is valid."""
    try:
        ZoneInfo(timezone_name)
    except Exception:
        raise SiteConfigValidationError(f"Timezone '{timezone_name}' is invalid.")


def _validate_target_repo(target_repo: str) -> None:
    """Ensure a target repo URL is plausible when present."""
    if not target_repo:
        return

    parsed = urlparse(target_repo)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SiteConfigValidationError(f"Target repo '{target_repo}' is invalid.")


def _validate_venues(venues: List[Venue]) -> None:
    """Validate venues for uniqueness and parser resolution."""
    if not venues:
        raise SiteConfigValidationError("At least one venue is required.")

    seen_keys = set()  # type: Set[str]
    for venue in venues:
        if not venue.key.strip():
            raise SiteConfigValidationError("Venue key cannot be empty.")
        if venue.key in seen_keys:
            raise SiteConfigValidationError(f"Duplicate venue key '{venue.key}'.")
        seen_keys.add(venue.key)

        if not venue.name.strip():
            raise SiteConfigValidationError(f"Venue '{venue.key}' must have a name.")

        _validate_venue_url(venue)
        _validate_parser_config(venue)
        _validate_parser_resolution(venue)


def _validate_venue_url(venue: Venue) -> None:
    """Ensure a venue URL uses http or https."""
    parsed = urlparse(venue.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SiteConfigValidationError(
            f"Venue '{venue.key}' has an invalid URL '{venue.url}'."
        )


def _validate_parser_config(venue: Venue) -> None:
    """Ensure parser_config is dict-like."""
    if venue.parser_config is not None and not isinstance(venue.parser_config, dict):
        raise SiteConfigValidationError(
            f"Venue '{venue.key}' must have a dict parser_config."
        )


def _validate_parser_resolution(venue: Venue) -> None:
    """Ensure the venue can resolve to a parser."""
    try:
        ParserRegistry.get_parser(venue)
    except ValueError as exc:
        raise SiteConfigValidationError(str(exc))
