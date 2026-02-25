from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

import jsonschema

from ..models.brewery import Brewery

_SCHEMA_PATH = Path(__file__).parent / "schemas" / "food-trucks-config.schema.json"


class ConfigValidationError(Exception):
    pass


@dataclass
class VenueList:
    list_name: str
    venues: List[Brewery]
    target_repo: str
    target_branch: str = "main"
    target_url: Optional[str] = None
    template_dir: Optional[str] = None


def load_venue_list(config_path: Union[str, Path]) -> VenueList:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open() as f:
        data = json.load(f)
    _validate_schema(data, path)
    return _deserialize(data)


def _validate_schema(data: dict, path: Path) -> None:
    with _SCHEMA_PATH.open() as f:
        schema = json.load(f)
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as exc:
        raise ConfigValidationError(
            f"Config file '{path}' failed schema validation: {exc.message}"
        ) from exc


def _deserialize(data: dict) -> VenueList:
    venues = [
        Brewery(
            key=v["key"],
            name=v["name"],
            url=v["url"],
            parser_config=v.get("parser_config"),
        )
        for v in data["venues"]
    ]
    return VenueList(
        list_name=data["list_name"],
        venues=venues,
        target_repo=data["target_repo"],
        target_branch=data.get("target_branch", "main"),
        target_url=data.get("target_url"),
        template_dir=data.get("template_dir"),
    )
