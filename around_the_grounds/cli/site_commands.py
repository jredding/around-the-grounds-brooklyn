"""CLI handlers for site configuration commands."""

import argparse
import asyncio
import json
import sys
from typing import List, Optional, Sequence

from ..config.validator import (
    SiteConfigValidationError,
    validate_site_config,
    validate_site_key_unique,
)
from ..config.writer import create_site_config
from ..models import SiteConfig, Venue
from ..utils.url_analyzer import AnalysisResult, UrlAnalyzer


def run_create_site(argv: Sequence[str]) -> int:
    """Create a new site config from analyzed URLs."""
    parser = _build_create_site_parser()
    args = parser.parse_args(list(argv))

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


async def _analyze_urls(urls: Sequence[str]) -> List[AnalysisResult]:
    analyzer = UrlAnalyzer()
    return await analyzer.analyze_many(urls)


def _build_create_site_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="around-the-grounds create-site",
        description="Create a site config from one or more source URLs.",
    )
    parser.add_argument("--key", required=True, help="Site key")
    parser.add_argument("--name", required=True, help="Site display name")
    parser.add_argument("--template", required=True, help="Template directory name")
    parser.add_argument("--timezone", required=True, help="IANA timezone name")
    parser.add_argument(
        "--url",
        dest="urls",
        action="append",
        required=True,
        help="Source URL to analyze and add",
    )
    parser.add_argument(
        "--target-repo",
        default="",
        help="Optional GitHub Pages repository URL",
    )
    parser.add_argument(
        "--generate-description",
        action="store_true",
        help="Enable generated daily description text for this site.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated config without writing it.",
    )
    return parser


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


def _site_to_dict(site: SiteConfig) -> dict:
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
    lines = ["Could not create site. Some URLs returned no events found:"]
    for result in results:
        lines.append(f"- {result.url}")
        for warning in result.warnings:
            lines.append(f"  hint: {warning}")
    return "\n".join(lines)


def main() -> None:
    sys.exit(run_create_site(sys.argv[1:]))
