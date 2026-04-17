"""Handler for the `check-url` subcommand."""

import argparse
import asyncio
import json
from typing import List, Optional, Sequence

from ..utils.url_analyzer import AnalysisResult, UrlAnalyzer


def run_check_url(args: argparse.Namespace) -> int:
    """Run the check-url subcommand with parsed argparse arguments."""
    parser_config: Optional[dict] = None
    raw_parser_config: Optional[str] = getattr(args, "parser_config", None)
    if raw_parser_config:
        try:
            parser_config = json.loads(raw_parser_config)
        except json.JSONDecodeError as exc:
            print(f"Error: invalid --parser-config JSON: {exc}")
            return 1
        if not isinstance(parser_config, dict):
            print("Error: --parser-config must decode to a JSON object.")
            return 1

    results = asyncio.run(
        _run_check_url(
            urls=args.urls,
            source_type=getattr(args, "source_type", None),
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


def _format_human_results(results: Sequence[AnalysisResult]) -> str:
    return "\n\n".join(_format_result(result) for result in results)


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
