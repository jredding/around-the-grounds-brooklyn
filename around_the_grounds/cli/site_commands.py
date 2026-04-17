"""Handlers for the `create-site` and `edit-site` subcommands."""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Dict, List, Sequence

from ..config.loader import load_site_from_path
from ..config.validator import (
    SiteConfigValidationError,
    validate_site_config,
    validate_site_key_unique,
)
from ..config.writer import (
    add_venues_to_site,
    create_site_config,
    remove_venue_from_site,
)
from ..models import SiteConfig, Venue
from ..utils.url_analyzer import AnalysisResult, UrlAnalyzer


def run_create_site(args: argparse.Namespace) -> int:
    """Create a new site config from analyzed URLs."""
    try:
        validate_site_key_unique(args.key)
    except SiteConfigValidationError as exc:
        print(f"Error: {exc}")
        return 1

    results = asyncio.run(_analyze_urls(args.urls))
    failed = [result for result in results if not result.success]
    if failed:
        print(_format_failed_urls(failed))
        return 1

    venues = _venues_from_results(results)
    site = SiteConfig(
        key=args.key,
        name=args.name,
        template=args.template,
        timezone=args.timezone,
        venues=venues,
        target_repo=args.target_repo,
        generate_description=args.generate_description,
    )

    try:
        validate_site_config(site)
    except SiteConfigValidationError as exc:
        print(f"Error: {exc}")
        return 1

    if args.dry_run:
        print(json.dumps(_site_to_dict(site), indent=2))
        return 0

    create_site_config(
        key=site.key,
        name=site.name,
        template=site.template,
        timezone=site.timezone,
        venues=site.venues,
        target_repo=site.target_repo,
        generate_description=site.generate_description,
    )
    print(f"Created site config at around_the_grounds/config/sites/{site.key}.json")
    return 0


def run_edit_site(args: argparse.Namespace) -> int:
    """Edit an existing site config: --show, --add-url, or --remove-venue."""
    sites_dir = _sites_dir()
    config_path = sites_dir / f"{args.site_key}.json"
    if not config_path.exists():
        print(f"Error: site '{args.site_key}' not found at {config_path}")
        return 1

    selected = [flag for flag in (args.show, args.add_url, args.remove_venue) if flag]
    if len(selected) != 1:
        print("Error: specify exactly one of --show, --add-url, or --remove-venue.")
        return 1

    if args.show:
        return _edit_site_show(config_path)

    if args.add_url:
        return _edit_site_add_url(
            sites_dir=sites_dir,
            config_path=config_path,
            site_key=args.site_key,
            url=args.add_url,
            dry_run=args.dry_run,
        )

    if args.remove_venue:
        return _edit_site_remove_venue(
            sites_dir=sites_dir,
            config_path=config_path,
            site_key=args.site_key,
            venue_key=args.remove_venue,
            dry_run=args.dry_run,
        )

    return 1  # unreachable — guarded above


def _edit_site_show(config_path: Path) -> int:
    site = load_site_from_path(config_path)
    print(json.dumps(_site_to_dict(site), indent=2))
    return 0


def _edit_site_add_url(
    sites_dir: Path,
    config_path: Path,
    site_key: str,
    url: str,
    dry_run: bool,
) -> int:
    results = asyncio.run(_analyze_urls([url]))
    failed = [result for result in results if not result.success]
    if failed:
        print(_format_failed_urls(failed))
        return 1

    new_venues = _venues_from_results(results)
    if not new_venues:
        print("Error: analyzer returned no usable venue config.")
        return 1

    existing_site = load_site_from_path(config_path)
    existing_keys = {venue.key for venue in existing_site.venues}
    for venue in new_venues:
        if venue.key in existing_keys:
            print(
                f"Error: venue key '{venue.key}' already exists in "
                f"{site_key}. Rename before re-adding."
            )
            return 1

    if dry_run:
        projected = SiteConfig(
            key=existing_site.key,
            name=existing_site.name,
            template=existing_site.template,
            timezone=existing_site.timezone,
            venues=existing_site.venues + new_venues,
            target_repo=existing_site.target_repo,
            generate_description=existing_site.generate_description,
        )
        print(json.dumps(_site_to_dict(projected), indent=2))
        return 0

    updated = add_venues_to_site(site_key, new_venues, sites_dir)
    added_keys = ", ".join(venue.key for venue in new_venues)
    print(
        f"Added venue(s) [{added_keys}] to {site_key}; "
        f"now {len(updated.venues)} venue(s)."
    )
    return 0


def _edit_site_remove_venue(
    sites_dir: Path,
    config_path: Path,
    site_key: str,
    venue_key: str,
    dry_run: bool,
) -> int:
    site = load_site_from_path(config_path)
    if not any(v.key == venue_key for v in site.venues):
        print(f"Error: venue '{venue_key}' not found in {site_key}.")
        return 1

    if dry_run:
        projected = SiteConfig(
            key=site.key,
            name=site.name,
            template=site.template,
            timezone=site.timezone,
            venues=[v for v in site.venues if v.key != venue_key],
            target_repo=site.target_repo,
            generate_description=site.generate_description,
        )
        print(json.dumps(_site_to_dict(projected), indent=2))
        return 0

    updated = remove_venue_from_site(site_key, venue_key, sites_dir)
    print(
        f"Removed venue '{venue_key}' from {site_key}; "
        f"now {len(updated.venues)} venue(s)."
    )
    return 0


async def _analyze_urls(urls: Sequence[str]) -> List[AnalysisResult]:
    analyzer = UrlAnalyzer()
    return await analyzer.analyze_many(urls)


def _venues_from_results(results: Sequence[AnalysisResult]) -> List[Venue]:
    venues: List[Venue] = []
    for result in results:
        if not result.venue_config:
            continue
        config = result.venue_config
        venues.append(
            Venue(
                key=config["key"],
                name=config["name"],
                url=config["url"],
                source_type=config["source_type"],
                parser_config=config.get("parser_config", {}),
            )
        )
    return venues


def _site_to_dict(site: SiteConfig) -> Dict[str, object]:
    return {
        "key": site.key,
        "name": site.name,
        "template": site.template,
        "timezone": site.timezone,
        "target_repo": site.target_repo,
        "generate_description": site.generate_description,
        "venues": [
            {
                "key": venue.key,
                "name": venue.name,
                "url": venue.url,
                "source_type": venue.source_type,
                "parser_config": venue.parser_config or {},
            }
            for venue in site.venues
        ],
    }


def _format_failed_urls(results: Sequence[AnalysisResult]) -> str:
    lines = ["Could not proceed. Some URLs returned no events found:"]
    for result in results:
        lines.append(f"- {result.url}")
        for warning in result.warnings:
            lines.append(f"  hint: {warning}")
    return "\n".join(lines)


def _sites_dir() -> Path:
    """Resolve the on-disk config/sites directory."""
    return Path(__file__).resolve().parents[1] / "config" / "sites"
