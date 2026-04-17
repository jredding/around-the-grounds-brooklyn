"""Handler for the `site lint` subcommand."""

import argparse
import json
from pathlib import Path
from typing import List, Optional

from ..config.loader import load_site_from_path
from ..config.validator import SiteConfigValidationError, validate_site_config


def run_site_lint(args: argparse.Namespace) -> int:
    """Validate one or all site configs statically."""
    sites_dir = _sites_dir()
    site_filter: Optional[str] = getattr(args, "site", None)

    paths = _collect_site_paths(sites_dir, site_filter)
    if not paths:
        if site_filter:
            print(f"Error: site '{site_filter}' not found in {sites_dir}.")
        else:
            print(f"Error: no site configs found in {sites_dir}.")
        return 1

    total_errors = 0
    for path in paths:
        errors = _lint_one(path)
        if errors:
            total_errors += len(errors)
            print(f"{path.name}:")
            for message in errors:
                print(f"  - {message}")
        else:
            print(f"{path.name}: ok")

    return 0 if total_errors == 0 else 1


def _collect_site_paths(sites_dir: Path, site_filter: Optional[str]) -> List[Path]:
    if site_filter:
        target = sites_dir / f"{site_filter}.json"
        return [target] if target.exists() else []
    if not sites_dir.is_dir():
        return []
    return sorted(sites_dir.glob("*.json"))


def _lint_one(path: Path) -> List[str]:
    messages: List[str] = []

    expected_key = path.stem
    try:
        site = load_site_from_path(path)
    except FileNotFoundError as exc:
        messages.append(str(exc))
        return messages
    except json.JSONDecodeError as exc:
        messages.append(f"invalid JSON: {exc}")
        return messages
    except KeyError as exc:
        messages.append(f"missing required field: {exc}")
        return messages

    if site.key != expected_key:
        messages.append(
            f"site key '{site.key}' does not match filename '{expected_key}.json'"
        )

    try:
        validate_site_config(site)
    except SiteConfigValidationError as exc:
        messages.append(str(exc))

    return messages


def _sites_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "sites"
