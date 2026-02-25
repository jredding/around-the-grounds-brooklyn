from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from .event import Location

VALID_SOURCE_TYPES = {"html", "ical", "api"}


@dataclass
class Venue:
    key: str
    name: str
    url: str
    source_type: str                           # "html" | "ical" | "api"

    timezone: Optional[str] = None            # ZoneInfo name; auto-resolved if None
    location: Optional[Location] = None
    parser_config: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.source_type not in VALID_SOURCE_TYPES:
            raise ValueError(
                f"Invalid source_type '{self.source_type}' for venue '{self.key}'. "
                f"Must be one of: {sorted(VALID_SOURCE_TYPES)}"
            )
