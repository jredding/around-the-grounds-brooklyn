from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Location:
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    timezone: Optional[str] = None  # ZoneInfo name e.g. "America/New_York"


@dataclass
class Event:
    venue_key: str
    venue_name: str
    title: str
    datetime_start: datetime                   # MUST be timezone-aware

    datetime_end: Optional[datetime] = None   # timezone-aware if present
    description: Optional[str] = None
    url: Optional[str] = None
    categories: List[str] = field(default_factory=list)
    cost: Optional[str] = None                # "free" or price string e.g. "$10"
    sold_out: bool = False
    location: Optional[Location] = None
    extraction_method: str = "html"           # "html" | "ical" | "api" | "ai-vision"

    def __post_init__(self):
        if self.datetime_start.tzinfo is None:
            raise ValueError(
                f"Event.datetime_start must be timezone-aware, got naive datetime for '{self.title}'"
            )
        if self.datetime_end is not None and self.datetime_end.tzinfo is None:
            raise ValueError(
                f"Event.datetime_end must be timezone-aware if provided, got naive datetime for '{self.title}'"
            )
