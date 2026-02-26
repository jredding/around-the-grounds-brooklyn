# ADDING NEW SITES AND VENUES

## Adding a New Venue to an Existing Site

If the venue's platform is already supported (WordPress, HTML with CSS selectors, or AJAX/JSON API), just add a venue entry to the site's JSON config — **no parser code needed**.

### 1. Choose the Right `source_type`

| Platform | `source_type` | When to Use |
|----------|---------------|-------------|
| WordPress REST API | `"wordpress"` | Site has `/wp-json/wp/v2/posts` endpoint |
| HTML with structured markup | `"html"` | Events are in repeating HTML containers with consistent CSS selectors |
| JSON/AJAX API | `"ajax"` | Site exposes events via a JSON endpoint |

### 2. Add Venue to Site Config

Edit the appropriate file in `around_the_grounds/config/sites/`:

**WordPress example** (`source_type: "wordpress"`):
```json
{
  "key": "new-venue",
  "name": "New Venue Name",
  "url": "https://newvenue.com",
  "source_type": "wordpress",
  "parser_config": {
    "api_path": "/wp-json/wp/v2/posts",
    "category_id": "123,456",
    "per_page": 20
  }
}
```

**HTML selector example** (`source_type: "html"`):
```json
{
  "key": "new-venue",
  "name": "New Venue Name",
  "url": "https://newvenue.com/events",
  "source_type": "html",
  "parser_config": {
    "event_container": ".event-item",
    "title_selector": ".event-title",
    "date_selector": ".event-date",
    "time_selector": ".event-time",
    "description_selector": ".event-description",
    "date_format": "auto"
  }
}
```

**AJAX/JSON API example** (`source_type: "ajax"`):
```json
{
  "key": "new-venue",
  "name": "New Venue Name",
  "url": "https://newvenue.com/events",
  "source_type": "ajax",
  "parser_config": {
    "api_url": "https://api.newvenue.com/v1/events",
    "method": "GET",
    "params": {"limit": 50},
    "response_path": "data.events",
    "field_map": {
      "title": "name",
      "date": "start_date",
      "start_time": "start_date",
      "end_time": "end_date",
      "description": "summary"
    }
  }
}
```

**AJAX with date placeholders** (replaced at runtime):
```json
{
  "params": {
    "query": "{\"startDate\":\"{{today_iso}}\",\"endDate\":\"{{end_date_iso}}\"}"
  }
}
```

### 3. Test

```bash
# Run the site to verify events are fetched
uv run around-the-grounds --site <site-key> --verbose

# Preview locally
uv run around-the-grounds --site <site-key> --preview
cd public && python -m http.server 8000
```

## Adding a New Site

### 1. Create Site Config

Create a new JSON file in `around_the_grounds/config/sites/<site-key>.json`:

```json
{
  "key": "my-new-site",
  "name": "My New Event Site",
  "template": "music",
  "timezone": "America/New_York",
  "target_repo": "https://github.com/username/atg-my-new-site.git",
  "generate_description": false,
  "venues": [
    {
      "key": "venue-one",
      "name": "Venue One",
      "url": "https://venueone.com/events",
      "source_type": "html",
      "parser_config": { ... }
    }
  ]
}
```

### 2. Choose or Create a Template

Available templates in `public_templates/`:
- `food-trucks` — dark theme, food truck oriented
- `music` — dark theme, music/show oriented
- `kids` — bright/playful theme, children's event oriented

To create a new template, add a directory under `public_templates/` with at least an `index.html`.

### 3. Set Up Target Repository

1. Create the GitHub repo (e.g., `atg-my-new-site`)
2. Enable GitHub Pages (Settings > Pages > Deploy from main branch root)
3. Install your GitHub App on the repo

### 4. Test and Deploy

```bash
uv run around-the-grounds --site my-new-site --preview   # Local preview
uv run around-the-grounds --site my-new-site --deploy     # Deploy to GitHub Pages
```

## Adding a Venue-Specific Parser (Unsupported Platform)

If the venue uses a platform not covered by the generic parsers:

### 1. Create Parser Class

```python
from .base import BaseParser
from ..models import Event
from typing import List
import aiohttp

class NewVenueParser(BaseParser):
    async def parse(self, session: aiohttp.ClientSession) -> List[Event]:
        try:
            soup = await self.fetch_page(session, self.venue.url)
            events = []

            # Extract events from HTML with error handling
            # Use self.logger for debugging
            # Use self.validate_event() for data validation

            valid_events = self.filter_valid_events(events)
            self.logger.info(f"Parsed {len(valid_events)} valid events")
            return valid_events

        except Exception as e:
            self.logger.error(f"Error parsing {self.venue.name}: {str(e)}")
            raise ValueError(f"Failed to parse venue website: {str(e)}")
```

### 2. Register Parser

In `parsers/registry.py`, add to the `_specific` dict:

```python
from .new_venue import NewVenueParser

class ParserRegistry:
    _specific: Dict[str, Type[BaseParser]] = {
        'new-venue-key': NewVenueParser,
        # ... existing parsers
    }
```

Venue-specific parsers take precedence over generic parsers. The registry looks up by `venue.key` first, then falls back to `venue.source_type`.

### 3. Add Venue to Site Config

Add the venue to the appropriate `config/sites/<key>.json`. The `source_type` doesn't matter for venue-specific parsers since the registry matches by key.

### 4. Write Tests

Create `tests/parsers/test_new_venue.py`:
- Test successful parsing with mock HTML
- Test error scenarios (network, parsing, validation)
- Test with real HTML fixtures if available
- Mock vision analysis if your parser uses it
