"""URL analysis helpers for suggesting parser configuration."""

import asyncio
import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urljoin, urlparse

import aiohttp
import anthropic
from bs4 import BeautifulSoup

from ..models import Event, Venue
from ..parsers.registry import ParserRegistry
from .http import default_request_headers

_DEFAULT_HTML_SELECTOR_PATTERNS: List[Dict[str, Any]] = [
    {
        "event_container": '[itemtype*="Event"]',
        "title_selector": '[itemprop="name"]',
        "date_selector": '[itemprop="startDate"]',
        "date_attribute": "content",
    },
    {
        "event_container": ".event-item",
        "title_selector": ".event-title",
        "date_selector": ".event-date",
    },
    {
        "event_container": ".event-card",
        "title_selector": ".event-title, .event-name, h3, h2",
        "date_selector": ".event-date, .date, time",
    },
    {
        "event_container": ".events-list > *",
        "title_selector": ".event-title, h3, h2",
        "date_selector": ".event-date, .date, time",
    },
    {
        "event_container": ".tribe-events-list .type-tribe_events",
        "title_selector": ".tribe-events-list-event-title a",
        "date_selector": ".tribe-event-schedule-details",
    },
    {
        "event_container": ".fc-event",
        "title_selector": ".fc-title, .fc-event-title",
        "date_selector": ".fc-time",
    },
    {
        "event_container": ".calendar-event",
        "title_selector": ".event-title, .event-name, h3",
        "date_selector": ".event-date, .date, time",
    },
    {
        "event_container": "article",
        "title_selector": "h2, h3",
        "date_selector": "time, .date, .event-date",
    },
]

_DEFAULT_WORDPRESS_CONFIGS: List[Dict[str, Any]] = [
    {
        "api_path": "/wp-json/tribe/events/v1/events",
        "per_page": 50,
        "response_path": "events",
        "field_map": {
            "title": "title",
            "date": "start_date",
            "end_time": "end_date",
            "description": "description",
        },
    },
    {
        "api_path": "/wp-json/wp/v2/posts",
        "per_page": 20,
    },
]

_AJAX_DISCOVERY_PATTERNS: Sequence[str] = (
    r'["\']?(https?://[^\s"\']+/api/events[^\s"\']*)["\']?',
    r'["\']?(https?://api\.[^\s"\']+/events[^\s"\']*)["\']?',
    r'fetch\(["\']([^"\']+)["\']',
    r'axios\.\w+\(["\']([^"\']+)["\']',
    r'url\s*[:=]\s*["\']([^"\']+(?:events|calendar|api|json)[^"\']*)["\']',
    r'data-api-url=["\']([^"\']+)["\']',
    r'data-events-url=["\']([^"\']+)["\']',
)

_SOURCE_PRIORITY = {
    "json-ld": 0,
    "wordpress": 1,
    "ajax": 2,
    "html": 3,
}


@dataclass
class StrategyAttempt:
    """One parser-family attempt for a URL."""

    strategy: str
    source_type: str
    applied: bool
    events_found: int = 0
    valid_events: int = 0
    timed_events: int = 0
    confidence: float = 0.0
    parser_config: Dict[str, Any] = field(default_factory=dict)
    sample_events: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnalysisResult:
    """Suggested parser shape for a URL."""

    url: str
    success: bool
    venue_config: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)
    sample_events: List[Dict[str, Any]] = field(default_factory=list)
    attempts: List[StrategyAttempt] = field(default_factory=list)
    message: str = "no events found"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["attempts"] = [attempt.to_dict() for attempt in self.attempts]
        return data


class UrlAnalyzer:
    """Analyze a URL using the current generic parser collection."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    async def analyze(
        self,
        url: str,
        source_type: Optional[str] = None,
        parser_config: Optional[Dict[str, Any]] = None,
    ) -> AnalysisResult:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(
            timeout=timeout,
            headers=default_request_headers(),
        ) as session:
            return await self._analyze_with_session(
                session,
                url=url,
                source_type=source_type,
                parser_config=parser_config,
            )

    async def analyze_many(
        self,
        urls: Sequence[str],
        source_type: Optional[str] = None,
        parser_config: Optional[Dict[str, Any]] = None,
    ) -> List[AnalysisResult]:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(
            timeout=timeout,
            headers=default_request_headers(),
        ) as session:
            tasks = [
                self._analyze_with_session(
                    session,
                    url=url,
                    source_type=source_type,
                    parser_config=parser_config,
                )
                for url in urls
            ]
            return await asyncio.gather(*tasks)

    async def _analyze_with_session(
        self,
        session: aiohttp.ClientSession,
        url: str,
        source_type: Optional[str] = None,
        parser_config: Optional[Dict[str, Any]] = None,
    ) -> AnalysisResult:
        normalized_url = normalize_url(url)
        key = self._generate_key(normalized_url)
        name = self._generate_name(key)
        result = AnalysisResult(url=normalized_url, success=False)
        page_html = await self._fetch_text(session, normalized_url)
        page_hints = self._page_hints_from_html(page_html)

        supported = ParserRegistry.get_generic_parsers()
        if source_type and source_type not in supported:
            result.warnings.append(
                f"Source type '{source_type}' is not supported by the generic parser registry."
            )
            return result

        for strategy_source_type in self._ordered_source_types(
            supported, source_type=source_type
        ):
            attempt = await self._probe_source_type(
                session,
                url=normalized_url,
                key=key,
                name=name,
                source_type=strategy_source_type,
                forced_parser_config=parser_config,
            )
            result.attempts.append(attempt)
            if attempt.valid_events > 0:
                result.success = True
                result.confidence = attempt.confidence
                result.warnings = list(dict.fromkeys(attempt.warnings))
                result.message = "events found"
                result.venue_config = {
                    "key": key,
                    "name": name,
                    "url": self._config_url(normalized_url, strategy_source_type),
                    "source_type": attempt.source_type,
                    "parser_config": attempt.parser_config,
                }
                result.sample_events = attempt.sample_events
                return result

        if (
            parser_config is None
            and source_type in (None, "html")
            and "html" in supported
        ):
            ai_attempt = await self._probe_ai_html(
                session,
                url=normalized_url,
                key=key,
                name=name,
            )
            if ai_attempt.applied or ai_attempt.error:
                result.attempts.append(ai_attempt)
            if ai_attempt.valid_events > 0:
                result.success = True
                result.confidence = ai_attempt.confidence
                result.warnings = list(dict.fromkeys(ai_attempt.warnings))
                result.message = "events found"
                result.venue_config = {
                    "key": key,
                    "name": name,
                    "url": normalized_url,
                    "source_type": "html",
                    "parser_config": ai_attempt.parser_config,
                }
                result.sample_events = ai_attempt.sample_events
                return result

        result.warnings = self._collect_result_warnings(result.attempts) + page_hints
        result.warnings = list(dict.fromkeys(result.warnings))
        return result

    def _ordered_source_types(
        self,
        supported: Dict[str, Any],
        source_type: Optional[str] = None,
    ) -> List[str]:
        if source_type:
            return [source_type]

        return sorted(
            supported.keys(),
            key=lambda item: (_SOURCE_PRIORITY.get(item, 99), item),
        )

    async def _probe_source_type(
        self,
        session: aiohttp.ClientSession,
        url: str,
        key: str,
        name: str,
        source_type: str,
        forced_parser_config: Optional[Dict[str, Any]] = None,
    ) -> StrategyAttempt:
        parser_class = ParserRegistry.get_generic_parsers()[source_type]
        configs = await self._candidate_configs(
            session, url=url, source_type=source_type, forced=forced_parser_config
        )
        best_attempt = StrategyAttempt(
            strategy=source_type,
            source_type=source_type,
            applied=False,
        )

        for config in configs:
            config_copy = dict(config)
            venue = Venue(
                key=key,
                name=name,
                url=self._config_url(url, source_type),
                source_type=source_type,
                parser_config=config_copy,
            )
            parser = parser_class(venue)
            try:
                events = await parser.parse(session)
            except Exception as exc:
                current_attempt = StrategyAttempt(
                    strategy=source_type,
                    source_type=source_type,
                    applied=False,
                    parser_config=config_copy,
                    error=str(exc),
                )
            else:
                current_attempt = self._build_attempt(
                    strategy=source_type,
                    source_type=source_type,
                    parser_config=config_copy,
                    events=events,
                )

            best_attempt = self._select_better_attempt(best_attempt, current_attempt)
            if current_attempt.valid_events > 0:
                return current_attempt

        return best_attempt

    async def _candidate_configs(
        self,
        session: aiohttp.ClientSession,
        url: str,
        source_type: str,
        forced: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if forced is not None:
            return [dict(forced)]

        if source_type == "json-ld":
            return [{}]

        if source_type == "wordpress":
            return self._dedupe_dicts(_DEFAULT_WORDPRESS_CONFIGS)

        if source_type == "ajax":
            return await self._ajax_candidate_configs(session, url)

        if source_type == "html":
            return self._dedupe_dicts(_DEFAULT_HTML_SELECTOR_PATTERNS)

        return [{}]

    async def _ajax_candidate_configs(
        self, session: aiohttp.ClientSession, url: str
    ) -> List[Dict[str, Any]]:
        html = await self._fetch_text(session, url)
        discovered_urls = await self._discover_ajax_urls(session, url)
        configs: List[Dict[str, Any]] = self._ajax_heuristic_configs(url, html)
        for api_url in discovered_urls:
            configs.append({"api_url": api_url})
        configs.append({})
        return self._dedupe_dicts(configs)

    async def _discover_ajax_urls(
        self, session: aiohttp.ClientSession, url: str
    ) -> List[str]:
        html = await self._fetch_text(session, url)
        if not html:
            return []

        matches: List[str] = []
        for pattern in _AJAX_DISCOVERY_PATTERNS:
            for match in re.findall(pattern, html, re.IGNORECASE):
                candidate = match[0] if isinstance(match, tuple) else match
                candidate = candidate.strip()
                if not candidate:
                    continue
                absolute_url = urljoin(url, candidate)
                if absolute_url not in matches:
                    matches.append(absolute_url)
        return matches

    def _ajax_heuristic_configs(
        self, url: str, html: Optional[str]
    ) -> List[Dict[str, Any]]:
        configs: List[Dict[str, Any]] = []
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()

        if hostname.endswith("caveat.nyc"):
            configs.append(
                {
                    "api_url": f"{parsed.scheme}://{parsed.netloc}/api/events/listings",
                    "response_path": "records",
                    "field_map": {
                        "title": "fields.Event",
                        "date": "fields.google_start_time",
                        "start_time": "fields.google_start_time",
                        "end_time": "fields.google_end_time",
                        "description": "fields.description",
                    },
                }
            )

        afton_key = self._extract_afton_api_key(html)
        if afton_key:
            configs.append(
                {
                    "api_url": f"https://aftontickets.com/api/get-events?key={afton_key}",
                    "response_path": "data",
                    "field_map": {
                        "title": "event_name",
                        "date": "start_time",
                        "start_time": "start_time",
                        "end_time": "end_time",
                    },
                }
            )

        return configs

    async def _probe_ai_html(
        self,
        session: aiohttp.ClientSession,
        url: str,
        key: str,
        name: str,
    ) -> StrategyAttempt:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return StrategyAttempt(
                strategy="ai-html",
                source_type="html",
                applied=False,
                error="ANTHROPIC_API_KEY not set",
            )

        html = await self._fetch_text(session, url)
        if not html:
            return StrategyAttempt(
                strategy="ai-html",
                source_type="html",
                applied=False,
                error="Could not fetch page for AI analysis.",
            )

        selectors = await self._ask_ai_for_selectors(
            api_key=api_key,
            url=url,
            html=self._trim_html(html),
        )
        if not selectors:
            return StrategyAttempt(
                strategy="ai-html",
                source_type="html",
                applied=True,
                error="AI could not identify event selectors.",
            )

        parser_class = ParserRegistry.get_generic_parsers()["html"]
        venue = Venue(
            key=key,
            name=name,
            url=url,
            source_type="html",
            parser_config=dict(selectors),
        )
        parser = parser_class(venue)
        try:
            events = await parser.parse(session)
        except Exception as exc:
            return StrategyAttempt(
                strategy="ai-html",
                source_type="html",
                applied=True,
                parser_config=dict(selectors),
                error=str(exc),
            )

        attempt = self._build_attempt(
            strategy="ai-html",
            source_type="html",
            parser_config=dict(selectors),
            events=events,
        )
        if attempt.valid_events > 0:
            attempt.warnings.append(
                "Parser config was inferred with AI and should be reviewed."
            )
            attempt.confidence = max(0.1, attempt.confidence - 0.15)
        return attempt

    async def _ask_ai_for_selectors(
        self, api_key: str, url: str, html: str
    ) -> Optional[Dict[str, Any]]:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        prompt = (
            "You are analyzing an HTML page to extract event listings.\n"
            f"URL: {url}\n\n"
            "Here is the trimmed HTML:\n"
            f"```html\n{html}\n```\n\n"
            "Return only JSON with CSS selectors for event extraction.\n"
            'Required keys: "event_container", "title_selector", "date_selector".\n'
            'Optional keys: "date_attribute", "time_selector", "description_selector", "date_format".\n'
            "If you cannot identify event listings, return {}."
        )

        try:
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            self.logger.debug("AI selector extraction failed: %s", exc)
            return None

        content_block = response.content[0]
        if hasattr(content_block, "text"):
            text = content_block.text.strip()  # type: ignore[attr-defined]
        else:
            text = str(content_block).strip()

        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            text = text.strip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            return None

        if not isinstance(result, dict):
            return None
        required = {"event_container", "title_selector", "date_selector"}
        if not required.issubset(result.keys()):
            return None
        return result

    def _build_attempt(
        self,
        strategy: str,
        source_type: str,
        parser_config: Dict[str, Any],
        events: Sequence[Event],
    ) -> StrategyAttempt:
        valid_events = [event for event in events if event.title and event.date]
        timed_events = [event for event in valid_events if event.start_time]

        warnings: List[str] = []
        normalized_config = dict(parser_config)
        if valid_events and len(timed_events) < len(valid_events):
            warnings.append("Some events were found without start times.")
            normalized_config.setdefault("times_optional", True)

        confidence = self._score_attempt(
            source_type=source_type,
            parser_config=normalized_config,
            valid_events=len(valid_events),
            timed_events=len(timed_events),
        )

        if (
            source_type == "wordpress"
            and normalized_config.get("api_path", "/wp-json/wp/v2/posts")
            == "/wp-json/wp/v2/posts"
        ):
            warnings.append("Generic WordPress post parsing may need manual review.")
            confidence = max(0.1, confidence - 0.1)

        return StrategyAttempt(
            strategy=strategy,
            source_type=source_type,
            applied=True,
            events_found=len(events),
            valid_events=len(valid_events),
            timed_events=len(timed_events),
            confidence=confidence,
            parser_config=normalized_config,
            sample_events=self._format_event_samples(valid_events),
            warnings=warnings,
        )

    def _score_attempt(
        self,
        source_type: str,
        parser_config: Dict[str, Any],
        valid_events: int,
        timed_events: int,
    ) -> float:
        if valid_events == 0:
            return 0.0

        base_scores = {
            "json-ld": 0.95,
            "wordpress": 0.8,
            "ajax": 0.75,
            "html": 0.65,
        }
        score = base_scores.get(source_type, 0.5)
        if timed_events == 0:
            score -= 0.15
        elif timed_events < valid_events:
            score -= 0.05

        if source_type == "html" and not parser_config.get("time_selector"):
            score -= 0.05

        if valid_events >= 5:
            score += 0.05

        return max(0.1, min(score, 0.99))

    def _select_better_attempt(
        self, current_best: StrategyAttempt, challenger: StrategyAttempt
    ) -> StrategyAttempt:
        current_score = (
            current_best.valid_events,
            current_best.confidence,
            current_best.events_found,
        )
        challenger_score = (
            challenger.valid_events,
            challenger.confidence,
            challenger.events_found,
        )
        if challenger_score > current_score:
            return challenger
        if not current_best.applied and challenger.applied:
            return challenger
        return current_best

    def _collect_result_warnings(
        self, attempts: Sequence[StrategyAttempt]
    ) -> List[str]:
        warnings: List[str] = []
        for attempt in attempts:
            warnings.extend(attempt.warnings)
        return list(dict.fromkeys(warnings))

    def _dedupe_dicts(self, configs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unique: List[Dict[str, Any]] = []
        seen = set()
        for config in configs:
            key = json.dumps(config, sort_keys=True, default=str)
            if key in seen:
                continue
            seen.add(key)
            unique.append(dict(config))
        return unique

    async def _fetch_text(
        self, session: aiohttp.ClientSession, url: str
    ) -> Optional[str]:
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                return await response.text()
        except aiohttp.ClientError:
            return None

    @staticmethod
    def _page_hints_from_html(html: Optional[str]) -> List[str]:
        if not html:
            return []

        hints: List[str] = []
        normalized = html.lower()

        if (
            '<div id="root"></div>' in normalized
            or "enable javascript to run this app" in normalized
        ) and "/static/js/main." in normalized:
            hints.append(
                "Page appears to be a JavaScript-rendered app shell; event data may require browser or API-specific parsing."
            )

        if (
            "afton-tickets-checkout" in normalized
            or "cdn1.aftontickets.com" in normalized
            or "afton" in normalized
        ):
            hints.append(
                "Page appears to embed an Afton Tickets widget; event data may require widget or API-specific parsing."
            )

        return hints

    @staticmethod
    def _extract_afton_api_key(html: Optional[str]) -> Optional[str]:
        if not html:
            return None
        match = re.search(r"apiKey:\s*['\"]([a-zA-Z0-9]+)['\"]", html)
        if not match:
            return None
        return match.group(1)

    @staticmethod
    def _format_event_samples(events: Sequence[Event]) -> List[Dict[str, Any]]:
        samples: List[Dict[str, Any]] = []
        for event in list(events)[:5]:
            sample: Dict[str, Any] = {
                "date": event.date.strftime("%Y-%m-%d"),
                "title": event.title,
            }
            if event.start_time:
                sample["start_time"] = event.start_time.strftime("%I:%M %p").lstrip("0")
            samples.append(sample)
        return samples

    @staticmethod
    def _config_url(url: str, source_type: str) -> str:
        if source_type != "wordpress":
            return url
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _generate_key(url: str) -> str:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        host_parts = hostname.split(".")
        base_host = host_parts[-2] if len(host_parts) >= 2 else hostname
        path_parts = [
            part
            for part in parsed.path.split("/")
            if part and part.lower() not in {"events", "calendar"}
        ]
        pieces = [base_host] + path_parts[:1]
        slug = "-".join(
            filter(
                None,
                (
                    re.sub(r"[^a-z0-9]+", "-", piece.lower()).strip("-")
                    for piece in pieces
                ),
            )
        )
        return slug or "venue"

    @staticmethod
    def _generate_name(key: str) -> str:
        return " ".join(word.capitalize() for word in key.split("-")) or key

    @staticmethod
    def _trim_html(html: str, max_chars: int = 15000) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(["script", "style", "noscript", "svg", "iframe"]):
            tag.decompose()
        trimmed = str(soup)
        if len(trimmed) > max_chars:
            return trimmed[:max_chars]
        return trimmed


def normalize_url(url: str) -> str:
    """Normalize user input into an absolute HTTP(S) URL."""
    cleaned = url.strip()
    if not cleaned:
        return cleaned
    parsed = urlparse(cleaned)
    if not parsed.scheme:
        return f"https://{cleaned}"
    return cleaned
