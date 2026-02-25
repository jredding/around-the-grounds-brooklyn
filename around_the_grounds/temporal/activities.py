"""Activity implementations for Temporal workflows."""

import json
import os
import shutil
import subprocess

# Import functions we need (these are safe to import in activities)
import sys
from datetime import datetime
from pathlib import Path
from subprocess import CalledProcessError
from typing import Any, Dict, List, Optional, Tuple

from temporalio import activity

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from around_the_grounds.main import (
    generate_web_data,
    load_brewery_config,
)
from around_the_grounds.models import Venue, Event
from around_the_grounds.scrapers import ScraperCoordinator
from around_the_grounds.scrapers.coordinator import ScrapingError


class ScrapeActivities:
    """Activities for scraping food truck data."""

    @staticmethod
    def _serialize_event(event: Event) -> Dict[str, Any]:
        """Convert an event to a JSON-serializable structure."""
        return {
            "venue_key": event.venue_key,
            "venue_name": event.venue_name,
            "title": event.title,
            "datetime_start": event.datetime_start.isoformat(),
            "datetime_end": event.datetime_end.isoformat() if event.datetime_end else None,
            "description": event.description,
            "extraction_method": event.extraction_method,
        }

    @staticmethod
    def _serialize_error(error: Optional[ScrapingError]) -> Optional[Dict[str, str]]:
        if not error:
            return None
        return {
            "venue_name": error.venue.name,
            "message": error.message,
            "user_message": error.to_user_message(),
        }

    @activity.defn
    async def test_connectivity(self) -> str:
        """Test activity connectivity."""
        return "Activity connectivity test successful"

    @activity.defn
    async def load_brewery_config(
        self, config_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Load brewery configuration and return as serializable data."""
        breweries = load_brewery_config(config_path)
        return [
            {
                "key": b.key,
                "name": b.name,
                "url": b.url,
                "parser_config": b.parser_config,
            }
            for b in breweries
        ]

    @activity.defn
    async def scrape_food_trucks(
        self, brewery_configs: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        """Scrape food truck data from all breweries."""
        # Convert dicts back to Venue objects
        breweries = [
            Venue(
                key=config["key"],
                name=config["name"],
                url=config["url"],
                source_type="html",
                parser_config=config["parser_config"],
            )
            for config in brewery_configs
        ]

        coordinator = ScraperCoordinator()
        events = await coordinator.scrape_all(breweries)
        errors = coordinator.get_errors()

        serialized_events = [self._serialize_event(event) for event in events]
        serialized_errors = [
            serialized_error
            for serialized_error in (
                self._serialize_error(error) for error in errors
            )
            if serialized_error
        ]

        return serialized_events, serialized_errors

    @activity.defn
    async def scrape_single_brewery(
        self, brewery_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Scrape one brewery and return serialized events and optional error."""
        brewery = Venue(
            key=brewery_config["key"],
            name=brewery_config["name"],
            url=brewery_config["url"],
            source_type="html",
            parser_config=brewery_config["parser_config"],
        )

        coordinator = ScraperCoordinator(max_concurrent=1)
        events, error = await coordinator.scrape_one(brewery)

        return {
            "events": [self._serialize_event(event) for event in events],
            "error": self._serialize_error(error),
        }


class DeploymentActivities:
    """Activities for web deployment and git operations."""

    @activity.defn
    async def generate_web_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate web-friendly JSON data from events and errors."""
        events = payload.get("events", [])
        errors = payload.get("errors")

        # Reconstruct events and use existing generate_web_data function
        reconstructed_events = []
        for event_data in events:
            event = Event(
                venue_key=event_data["venue_key"],
                venue_name=event_data["venue_name"],
                title=event_data["title"],
                datetime_start=datetime.fromisoformat(event_data["datetime_start"]),
                datetime_end=(
                    datetime.fromisoformat(event_data["datetime_end"])
                    if event_data["datetime_end"]
                    else None
                ),
                description=event_data["description"],
                extraction_method=event_data["extraction_method"],
            )
            reconstructed_events.append(event)

        error_messages: List[str] = []
        if errors:
            for error in errors:
                if isinstance(error, dict):
                    if "user_message" in error and error["user_message"]:
                        error_messages.append(str(error["user_message"]))
                    elif "venue_name" in error and error["venue_name"]:
                        error_messages.append(
                            f"Failed to fetch information for venue: {error['venue_name']}"
                        )
                elif isinstance(error, str) and error:
                    error_messages.append(error)

        error_messages = list(dict.fromkeys(error_messages))

        return await generate_web_data(reconstructed_events, error_messages)

    @activity.defn
    async def deploy_to_git(self, params: Dict[str, Any]) -> bool:
        """Deploy web data to git repository."""
        import tempfile

        from around_the_grounds.utils.github_auth import GitHubAppAuth

        # Extract parameters
        web_data = params["web_data"]
        repository_url = params["repository_url"]

        try:
            activity.logger.info(
                f"Starting deployment with {web_data.get('total_events', 0)} events"
            )

            # Create temporary directory for git operations
            with tempfile.TemporaryDirectory() as temp_dir:
                repo_dir = Path(temp_dir) / "repo"

                # Clone the repository
                activity.logger.info(
                    f"Cloning repository {repository_url} to {repo_dir}"
                )
                subprocess.run(
                    ["git", "clone", repository_url, str(repo_dir)],
                    check=True,
                    capture_output=True,
                )

                # Configure git user in the cloned repository
                subprocess.run(
                    ["git", "config", "user.email", "steve.androulakis@gmail.com"],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "config", "user.name", "Steve Androulakis"],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                )

                # Copy template files from public_template to cloned repo
                public_template_dir = Path.cwd() / "public_template"
                target_public_dir = repo_dir / "public"

                activity.logger.info(
                    f"Copying template files from {public_template_dir}"
                )
                shutil.copytree(
                    public_template_dir, target_public_dir, dirs_exist_ok=True
                )

                # Write generated web data to cloned repository
                json_path = target_public_dir / "data.json"
                with open(json_path, "w") as f:
                    json.dump(web_data, f, indent=2)

                activity.logger.info(f"Generated web data file: {json_path}")

                # Add all files in public directory
                subprocess.run(
                    ["git", "add", "public/"],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                )

                # Check if there are changes to commit
                result = subprocess.run(
                    ["git", "diff", "--staged", "--quiet"],
                    cwd=repo_dir,
                    capture_output=True,
                )
                if result.returncode == 0:
                    activity.logger.info("No changes to deploy")
                    return True

                # Commit changes
                commit_msg = f"🚚 Update food truck data - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                subprocess.run(
                    ["git", "commit", "-m", commit_msg],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                )

                # Set up GitHub App authentication and configure remote
                auth = GitHubAppAuth(repository_url)
                access_token = auth.get_access_token()

                authenticated_url = f"https://x-access-token:{access_token}@github.com/{auth.repo_owner}/{auth.repo_name}.git"
                subprocess.run(
                    ["git", "remote", "set-url", "origin", authenticated_url],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                )

                # Push to origin
                subprocess.run(
                    ["git", "push", "origin", "main"],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                )
                activity.logger.info("Deployed to git! Changes will be live shortly.")

                return True

        except CalledProcessError as e:
            error_msg = e.stderr.decode("utf-8") if e.stderr else str(e)
            activity.logger.error(f"Git operation failed: {error_msg}")
            raise ValueError(f"Failed to deploy to git: {error_msg}")
        except Exception as e:
            activity.logger.error(f"Error during deployment: {e}")
            raise ValueError(f"Failed to deploy to git: {e}")
