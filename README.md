# Around the Grounds 🍺🚚

A multi-site event aggregator platform built in Python. Each site is defined by a JSON config file — no new parser code needed unless the site uses an unsupported platform. Currently tracks food truck schedules, indie music shows, and children's events across Brooklyn and Seattle.

## Features

- 🔄 **Multi-Site Support**: Independent site configs for different event domains (food trucks, music, kids events)
- 🔌 **Generic Parsers**: Config-driven parsers for WordPress, HTML (CSS selectors), and AJAX/JSON APIs
- 🖼️ **AI Vision Analysis**: Extracts vendor names from food truck images using Claude Vision API
- 🎋 **AI Haiku Generation**: Creates contextual, seasonal haikus about daily food truck scenes
- 🌐 **Auto-Deployment**: Git-based deployment to GitHub Pages via GitHub App authentication
- ☁️ **Cloud Run Jobs**: Google Cloud Run with Cloud Scheduler for daily automated updates
- ⏰ **Temporal Workflows**: Reliable scheduling with cloud or local execution
- 🧪 **Comprehensive Testing**: 344 tests covering unit, integration, and error scenarios

## How It Works

This repository contains the **scraping and scheduling engine**. When run with `--deploy`, it:

1. **Scrapes** venue websites for event data
2. **Generates AI content**: Creates daily haikus and extracts vendor names from images (when `ANTHROPIC_API_KEY` is set)
3. **Copies** site-specific templates from `public_templates/<template>/` to target repository root
4. **Generates** static site data (`data.json`) in target repository root
5. **Force pushes** to target repo, which is served by GitHub Pages

**Two-Repository Architecture:**
- **Source repo** (this one): Contains scraping code, parsers, site configs, per-site templates
- **Target repos** (e.g., `jredding/atg-ballard-food-trucks`): Receive complete websites, served via GitHub Pages

## Quick Start

### Installation
```bash
git clone https://github.com/jredding/around-the-grounds-brooklyn
cd around-the-grounds-brooklyn
uv sync
```

### Basic CLI Usage
```bash
uv run around-the-grounds              # Show 7-day schedule (default: ballard-food-trucks)
uv run around-the-grounds --verbose    # With detailed logging
uv run around-the-grounds --preview    # Generate local preview files
uv run around-the-grounds --deploy     # Scrape and deploy to web

# Run a specific site
uv run around-the-grounds --site ballard-food-trucks
uv run around-the-grounds --site park-slope-music
uv run around-the-grounds --site childrens-events

# Run all configured sites
uv run around-the-grounds --site all

# Combine flags
uv run around-the-grounds --site ballard-food-trucks --deploy --verbose
```

### Example Output
```
🍺 Around the Grounds - Food Truck Tracker
==================================================
Found 23 food truck events:

🎋 Today's Haiku:
🍂 Autumn mist rolls in—
Plaza Garcia's warmth glows
at Obec's wood door 🍺

📅 Saturday, July 05, 2025
  🚚 Woodshop BBQ @ Stoup Brewing - Ballard 01:00 PM - 08:00 PM
  🚚 Kaosamai Thai @ Obec Brewing 04:00 PM - 08:00 PM

📅 Sunday, July 06, 2025
  🚚 Burger Planet @ Stoup Brewing - Ballard 01:00 PM - 07:00 PM
  🚚 TOLU 🖼️🤖 @ Urban Family Brewing 01:00 PM - 07:00 PM
```

## Web Deployment (Optional)

To deploy a live website, you need a **target repository** and **GitHub App** for authentication.

### Prerequisites
- Target GitHub repository (e.g., `jredding/atg-ballard-food-trucks`)
- GitHub App with repository access installed on target repos
- GitHub Pages enabled on target repos (deploy from main branch root)

### GitHub App Setup

1. **Create GitHub App** at https://github.com/settings/apps
   - **Repository permissions**: Contents (Read & Write), Metadata (Read)
   - **Generate private key** and save the `.pem` file
   - **Install app** on your target repository

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your GitHub App credentials:
   # GITHUB_APP_ID=123456
   # GITHUB_CLIENT_ID=your-github-client-id
   # GITHUB_APP_PRIVATE_KEY_B64=<base64-encoded-private-key>
   ```
   
   **Note:** The system includes working defaults for `GITHUB_APP_ID` and `GITHUB_CLIENT_ID`. You only need to override these if using a different GitHub App.

3. **Deploy Data**
   ```bash
   uv run around-the-grounds --deploy
   ```

This will copy site-specific templates and generate fresh data in the target repository configured in the site's JSON config, triggering GitHub Pages deployment.

## Local Preview & Testing

Before deploying, you can preview changes locally:

```bash
# Generate web files locally for testing
uv run around-the-grounds --preview

# Serve locally and view in browser
cd public && python -m http.server 8000
# Visit: http://localhost:8000

# Automated testing methods:
# Test data.json endpoint
cd public && timeout 10s python -m http.server 8000 > /dev/null 2>&1 & sleep 1 && curl -s http://localhost:8000/data.json | head -20 && pkill -f "python -m http.server" || true

# Test for specific event data (e.g., Sunday events)
cd public && timeout 10s python -m http.server 8000 > /dev/null 2>&1 & sleep 1 && curl -s http://localhost:8000/data.json | grep "2025-07-06" && pkill -f "python -m http.server" || true

# Test full homepage (basic connectivity)
cd public && timeout 10s python -m http.server 8000 > /dev/null 2>&1 & sleep 1 && curl -s http://localhost:8000/ > /dev/null && echo "✅ Homepage loads" && pkill -f "python -m http.server" || echo "❌ Homepage failed"

# Test JavaScript rendering (requires Node.js/puppeteer - optional)
# npm install -g puppeteer
cd public && timeout 15s python -m http.server 8000 > /dev/null 2>&1 & sleep 2 && \
  node -e "
const puppeteer = require('puppeteer');
(async () => {
  const browser = await puppeteer.launch({headless: true});
  const page = await browser.newPage();
  await page.goto('http://localhost:8000');
  await page.waitForSelector('.day-section', {timeout: 5000});
  const dayHeaders = await page.$$eval('.day-header', els => els.map(el => el.textContent));
  console.log('✅ Rendered days:', dayHeaders.slice(0,2).join(', '));
  const eventCount = await page.$$eval('.truck-item', els => els.length);
  console.log('✅ Rendered events:', eventCount);
  await browser.close();
})().catch(e => console.log('❌ JS render test failed:', e.message));
" && pkill -f "python -m http.server" || echo "❌ Install puppeteer for JS testing: npm install -g puppeteer"
```

**What `--preview` does:**
1. Scrapes fresh data from all venue websites for the selected site
2. Copies site-specific templates from `public_templates/<template>/` to `public/`
3. Generates `data.json` with current event data
4. Creates complete website in `public/` directory (git-ignored)

This allows you to test web interface changes, verify data accuracy, and debug issues before deploying to production.

## Scheduled Updates

Use **Temporal workflows** to run automatic updates with a persistent worker system.

### Setup Temporal Worker
```bash
# Start worker (runs continuously)
uv run python -m around_the_grounds.temporal.worker

# Create schedule (runs every 30 minutes) 
uv run python -m around_the_grounds.temporal.schedule_manager create --schedule-id daily-scrape --interval 30
```

### Schedule Management
```bash
# List all schedules
uv run python -m around_the_grounds.temporal.schedule_manager list

# Pause/unpause schedules
uv run python -m around_the_grounds.temporal.schedule_manager pause --schedule-id daily-scrape
uv run python -m around_the_grounds.temporal.schedule_manager unpause --schedule-id daily-scrape

# Trigger immediate execution
uv run python -m around_the_grounds.temporal.schedule_manager trigger --schedule-id daily-scrape

# Delete schedule
uv run python -m around_the_grounds.temporal.schedule_manager delete --schedule-id daily-scrape
```

Workers can run on any system (local, cloud, Synology NAS) and will receive scheduled workflow executions from Temporal.

### Production Deployment via CI/CD

For automated production updates using Docker and Watchtower:

A **Temporal Worker** runs in a Docker container and continuously listens for scheduled workflow executions. This worker will automatically pick up and execute any schedules you've configured (see [Scheduled Updates](#scheduled-updates) section above for creating schedules).

**Example CICD Flow:**
1. **Code changes** → GitHub Actions → Docker Hub (4 minutes)
2. **Watchtower** detects new image → pulls and restarts worker container (every 5 minutes)
3. **Temporal Worker** in container listens for scheduled workflow executions
4. **Schedules trigger** automatically (every 30 minutes, etc.) or manually starting workflows via UI/CLI/API
5. **Worker executes** scraping and deployment workflow which pushes to the target repository
6. **Data deploys** automatically to target repository → live website updates (GitHub Pages)

The containerized worker provides reliable, continuous execution of scheduled food truck data updates without manual intervention.

**Alternative: Google Cloud Run** (current production setup):
```bash
# 3 Cloud Run Jobs (one per site), triggered daily by Cloud Scheduler:
#   - atg-ballard-food-trucks  (8:00 AM PT daily)
#   - atg-park-slope-music     (8:15 AM ET daily)
#   - atg-childrens-events     (8:30 AM ET daily)
# Each job runs: /bin/sh -c "/usr/local/bin/uv run around-the-grounds --site <key> --deploy"
# Image: us-central1-docker.pkg.dev/event-curation/around-the-grounds/app:latest
```

## Configuration

### Configured Sites

Site configs live in `around_the_grounds/config/sites/`. Each site has its own venues, template, timezone, and target deployment repo.

| Site Key | Name | Venues | Template | Target Repo |
|---|---|---|---|---|
| `ballard-food-trucks` | Ballard Food Trucks | Stoup, Bale Breaker, Obec, Urban Family, Wheelie Pop, Chuck's, Saleh's | `food-trucks` | `atg-ballard-food-trucks` |
| `park-slope-music` | Park Slope Indie Music Events | Union Hall, Littlefield | `music` | `atg-park-slope-music` |
| `childrens-events` | Brooklyn Children's Events | MacaroniKid, Little Kid Big City | `kids` | `atg-childrens-events` |

### Environment Variables
```bash
# Optional: AI features (vision analysis + haiku generation)
ANTHROPIC_API_KEY=your-anthropic-api-key  # Enables vendor name extraction from images and daily haiku generation

# Required for web deployment
GITHUB_APP_ID=123456
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_APP_PRIVATE_KEY_B64=base64-encoded-private-key
GIT_REPOSITORY_URL=https://github.com/username/target-repo.git

# Optional: Temporal configuration (defaults to localhost)
TEMPORAL_ADDRESS=your-namespace.acct.tmprl.cloud:7233
TEMPORAL_API_KEY=your-temporal-api-key
```

### Haiku Prompt Template
- Default prompt: `around_the_grounds/config/haiku_prompt.txt`
- Override via env var: `HAIKU_PROMPT_FILE=/path/to/custom_prompt.txt`
- Template placeholders: `{date}`, `{truck_name}`, `{venue_name}`, `{events_summary}`

Copy the default file and tweak the location descriptions, tone, or formatting to suit your own food truck scene. Missing placeholders trigger a safe fallback to the built-in prompt.

### Custom Repository
```bash
# Deploy to specific repository (overrides site config target_repo)
uv run around-the-grounds --site ballard-food-trucks --deploy --git-repo https://github.com/username/custom-repo.git

# Or set environment variable
export GIT_REPOSITORY_URL="https://github.com/username/custom-repo.git"
uv run around-the-grounds --deploy
```

## Development

### Setup
```bash
uv sync --dev                          # Install dev dependencies
```

### Local Development Workflow
```bash
# 1. Make code changes
# 2. Test locally with preview
uv run around-the-grounds --preview
cd public && python -m http.server 8000

# Quick verification tests:
cd public && timeout 10s python -m http.server 8000 > /dev/null 2>&1 & sleep 1 && curl -s http://localhost:8000/data.json | head -5 && pkill -f "python -m http.server" || true

# 3. Run tests
uv run python -m pytest

# 4. Deploy when ready
uv run around-the-grounds --deploy
```

### Testing  
```bash
uv run python -m pytest                # Run all 344 tests
uv run python -m pytest -v             # Verbose output
uv run python -m pytest tests/parsers/ # Parser-specific tests
```

### Code Quality
```bash
uv run black .                         # Format code
uv run flake8                          # Lint code  
uv run mypy around_the_grounds/        # Type checking
```

### Adding New Sites/Venues
For sites using supported platforms (WordPress, HTML with CSS selectors, AJAX/JSON API):
1. Create a new JSON config file in `around_the_grounds/config/sites/`
2. No parser code needed — just configure `source_type` and `parser_config`

For sites with unsupported platforms:
1. Create a venue-specific parser class in `around_the_grounds/parsers/`
2. Register it in `around_the_grounds/parsers/registry.py`
3. Add venue config to your site JSON
4. Write tests in `tests/parsers/`

See [CLAUDE.md](CLAUDE.md) for detailed development documentation.

## Architecture

- **CLI Tool**: `around_the_grounds/main.py` - Multi-site entry point with `--site` flag
- **Site Configs**: JSON files in `config/sites/` define venues, templates, timezones, target repos
- **Generic Parsers**: `parsers/generic/` — WordPress, HTML selector, AJAX (config-driven)
- **Venue-Specific Parsers**: `parsers/` — 7 Ballard food truck parsers (hand-written)
- **Registry**: Two-tier lookup — venue key (specific) then source_type (generic)
- **Scrapers**: Async coordinator with error handling and retries
- **AI Utils**: Vision analyzer for vendor identification, haiku generator for daily scenes
- **Temporal**: Workflow orchestration for reliable scheduling
- **Web Templates**: Per-site templates in `public_templates/<template>/` (deployed to GitHub Pages)
- **Tests**: 344 tests covering unit, integration, generic parsers, and error scenarios

## Requirements

- Python 3.8+
- Dependencies: `aiohttp`, `beautifulsoup4`, `temporalio`, `anthropic` (optional)

## License

MIT License
