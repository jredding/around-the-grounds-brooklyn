from dataclasses import dataclass, field
from typing import List

from .brewery import Venue


@dataclass
class SiteConfig:
    key: str
    name: str
    template: str
    timezone: str
    venues: List[Venue]
    target_repo: str = ""
    generate_description: bool = True
