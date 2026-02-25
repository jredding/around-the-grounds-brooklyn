"""Shared data models for Temporal workflows."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class WorkflowParams:
    """Parameters for the food truck workflow."""

    venues_config: Optional[str] = None
    deploy: bool = False
    max_parallel_scrapes: int = 10


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""

    success: bool
    message: str
    events_count: Optional[int] = None
    errors: Optional[List[str]] = None
    deployed: bool = False
