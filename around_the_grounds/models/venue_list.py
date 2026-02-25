from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from .venue import Venue


@dataclass
class VenueList:
    list_name: str
    venues: List[Venue]
    target_repo: str
    target_branch: str = "main"
    template_dir: Optional[str] = None

    def __post_init__(self):
        keys = [v.key for v in self.venues]
        duplicates = {k for k in keys if keys.count(k) > 1}
        if duplicates:
            raise ValueError(
                f"Duplicate venue keys in VenueList '{self.list_name}': {sorted(duplicates)}"
            )
        if not self.venues:
            raise ValueError(f"VenueList '{self.list_name}' must contain at least one venue")
