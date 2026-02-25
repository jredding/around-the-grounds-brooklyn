import json
import pytest
from pathlib import Path
from around_the_grounds.config.loader import (
    load_venue_list,
    VenueList,
    ConfigValidationError,
)


def test_load_venue_list_returns_venue_list(tmp_path: Path) -> None:
    config = {
        "list_name": "Test List",
        "target_repo": "https://github.com/test/repo.git",
        "venues": [
            {"key": "test-venue", "name": "Test Venue", "url": "https://example.com", "source_type": "html"}
        ],
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))
    result = load_venue_list(config_file)
    assert isinstance(result, VenueList)
    assert result.list_name == "Test List"
    assert len(result.venues) == 1
    assert result.venues[0].key == "test-venue"


def test_load_venue_list_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load_venue_list("/nonexistent/path/config.json")


def test_load_venue_list_raises_config_validation_error(tmp_path: Path) -> None:
    config = {"list_name": "Missing venues"}  # missing required "venues" and "target_repo"
    config_file = tmp_path / "bad_config.json"
    config_file.write_text(json.dumps(config))
    with pytest.raises(ConfigValidationError):
        load_venue_list(config_file)


def test_load_venue_list_default_target_branch(tmp_path: Path) -> None:
    config = {
        "list_name": "Test",
        "target_repo": "https://github.com/test/repo.git",
        "venues": [
            {"key": "v1", "name": "V1", "url": "https://example.com", "source_type": "html"}
        ],
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))
    result = load_venue_list(config_file)
    assert result.target_branch == "main"
