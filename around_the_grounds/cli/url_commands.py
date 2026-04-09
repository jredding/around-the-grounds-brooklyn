"""CLI handlers for URL analysis commands."""

import argparse
import asyncio
import json
import sys
from typing import List, Optional, Sequence

from ..utils.url_analyzer import AnalysisResult, UrlAnalyzer


def run(argv: Sequence[str]) -> int:
    """Run the URL-analysis command group."""
    parser = _build_parser()
    args = parser.parse_args(list(argv))

    parser_config = None
    if args.parser_config:
        try:
            parser_config = json.loads(args.parser_config)
        except json.JSONDecodeError as exc:
            print(f"Error: invalid --parser-config JSON: {exc}")
            return 1
        if not isinstance(parser_config, dict):
            print("Error: --parser-config must decode to a JSON object.")
            return 1

    results = asyncio.run(
        _run_check_url(
            urls=args.urls,
            source_type=args.source_type,
            parser_config=parser_config,
        )
    )

    if args.json:
        print(json.dumps([result.to_dict() for result in results], indent=2))
    else:
        print(_format_human_results(results))

    return 0 if all(result.success for result in results) else 1


async def _run_check_url(
    urls: Sequence[str],
    source_type: Optional[str] = None,
    parser_config: Optional[dict] = None,
) -> List[AnalysisResult]:
    analyzer = UrlAnalyzer()
    return await analyzer.analyze_many(
        urls,
        source_type=source_type,
        parser_config=parser_config,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="around-the-grounds check-url",
        description="Inspect one or more URLs and suggest parser configuration.",
    )
    parser.add_argument("urls", nargs="+", help="URL(s) to analyze")
    parser.add_argument(
        "--source-type",
        help="Force a specific generic parser family to test.",
    )
    parser.add_argument(
        "--parser-config",
        help="JSON object for directed parser testing.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output.",
    )
    return parser


def _format_human_results(results: Sequence[AnalysisResult]) -> str:
    blocks = [_format_result(result) for result in results]
    return "\n\n".join(blocks)


def _format_result(result: AnalysisResult) -> str:
    lines = [f"URL: {result.url}"]

    if result.success and result.venue_config:
        lines.append(f"Suggested source type: {result.venue_config['source_type']}")
        lines.append(f"Confidence: {result.confidence:.2f}")
        lines.append("Suggested parser config:")
        lines.append(json.dumps(result.venue_config["parser_config"], indent=2))
        if result.sample_events:
            lines.append("Sample events:")
            for sample in result.sample_events:
                date_str = sample.get("date", "unknown-date")
                title = sample.get("title", "Untitled event")
                time_str = sample.get("start_time")
                if time_str:
                    lines.append(f"- {date_str} {time_str} | {title}")
                else:
                    lines.append(f"- {date_str} | {title}")
    else:
        lines.append("No events found.")

    if result.warnings:
        lines.append("Warnings:")
        for warning in result.warnings:
            lines.append(f"- {warning}")

    if not result.success and result.attempts:
        attempted = ", ".join(attempt.strategy for attempt in result.attempts)
        lines.append(f"Attempted strategies: {attempted}")

    return "\n".join(lines)


def main() -> None:
    sys.exit(run(sys.argv[1:]))
