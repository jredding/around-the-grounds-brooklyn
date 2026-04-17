"""Helpers for writing site configuration files."""

import json
import os
import tempfile
from pathlib import Path
from typing import List, Optional, Set

from ..models import SiteConfig, Venue
from .loader import load_site_from_path


def _default_sites_dir() -> Path:
    """Return the default config/sites directory."""
    return Path(__file__).parent / "sites"


def _site_path(site_key: str, sites_dir: Optional[Path] = None) -> Path:
    """Return the JSON path for a site key."""
    directory = sites_dir or _default_sites_dir()
    return directory / f"{site_key}.json"


def _venue_to_dict(venue: Venue) -> dict:
    """Serialize a Venue to the repo's JSON shape."""
    return {
        "key": venue.key,
        "name": venue.name,
        "url": venue.url,
        "source_type": venue.source_type,
        "parser_config": venue.parser_config or {},
    }


def _site_to_dict(site: SiteConfig) -> dict:
    """Serialize a SiteConfig to the repo's JSON shape."""
    return {
        "key": site.key,
        "name": site.name,
        "template": site.template,
        "timezone": site.timezone,
        "target_repo": site.target_repo,
        "generate_description": site.generate_description,
        "venues": [_venue_to_dict(venue) for venue in site.venues],
    }


def save_site_config(site: SiteConfig, path: Optional[Path] = None) -> Path:
    """Atomically write a SiteConfig to disk."""
    target_path = path or _site_path(site.key)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".tmp",
            dir=str(target_path.parent),
            delete=False,
        ) as temp_file:
            json.dump(_site_to_dict(site), temp_file, indent=2)
            temp_file.write("\n")
            temp_path = Path(temp_file.name)

        os.replace(str(temp_path), str(target_path))
        return target_path
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def create_site_config(
    key: str,
    name: str,
    template: str,
    timezone: str,
    venues: List[Venue],
    target_repo: str = "",
    generate_description: bool = True,
    path: Optional[Path] = None,
) -> SiteConfig:
    """Create and persist a new site config."""
    target_path = path or _site_path(key)
    if target_path.exists():
        raise FileExistsError(f"Site config already exists: {target_path}")

    site = SiteConfig(
        key=key,
        name=name,
        template=template,
        timezone=timezone,
        venues=venues,
        target_repo=target_repo,
        generate_description=generate_description,
    )
    save_site_config(site, target_path)
    return site


def add_venues_to_site(
    site_key: str,
    venues: List[Venue],
    sites_dir: Optional[Path] = None,
) -> SiteConfig:
    """Append venues to an existing site config and persist the result."""
    config_path = _site_path(site_key, sites_dir)
    site = load_site_from_path(config_path)

    existing_keys = {venue.key for venue in site.venues}
    duplicate_keys = _find_duplicate_venue_keys(venues, existing_keys)
    if duplicate_keys:
        keys = ", ".join(sorted(duplicate_keys))
        raise ValueError(f"Venue keys already exist: {keys}")

    site.venues.extend(venues)
    save_site_config(site, config_path)
    return site


def remove_venue_from_site(
    site_key: str,
    venue_key: str,
    sites_dir: Optional[Path] = None,
) -> SiteConfig:
    """Remove a single venue from an existing site config and persist the result."""
    config_path = _site_path(site_key, sites_dir)
    site = load_site_from_path(config_path)

    filtered_venues = [venue for venue in site.venues if venue.key != venue_key]
    if len(filtered_venues) == len(site.venues):
        raise KeyError(f"Venue not found: {venue_key}")

    site.venues = filtered_venues
    save_site_config(site, config_path)
    return site


def _find_duplicate_venue_keys(
    venues: List[Venue], existing_keys: Optional[Set[str]] = None
) -> Set[str]:
    """Return duplicate keys from the incoming list plus any existing conflicts."""
    duplicates = set()
    seen = set(existing_keys or set())

    for venue in venues:
        if venue.key in seen:
            duplicates.add(venue.key)
            continue
        seen.add(venue.key)

    return duplicates
