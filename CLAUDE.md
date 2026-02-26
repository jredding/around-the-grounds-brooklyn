# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Around the Grounds is a multi-site event aggregator platform. Each site is defined by a JSON config file in `config/sites/` — no new parser code is needed unless the site uses an unsupported platform. The project features:
- **Multi-site support** with independent site configs for different event domains (food trucks, music, kids events)
- **Generic parser system** with platform-based parsers (WordPress, HTML selector, AJAX/JSON API) plus venue-specific parsers
- **Web interface** with per-site templates and automatic deployment to GitHub Pages
- **Async web scraping** with concurrent processing of multiple venue websites
- **AI vision analysis** using Claude Vision API to extract vendor names from food truck logos/images
- **AI haiku generation** using Claude Sonnet to create contextual, poetic descriptions of daily food truck scenes
- **Auto-deployment** with git integration for seamless web updates to GitHub Pages
- **Cloud Run Jobs** with Cloud Scheduler for daily automated site updates
- **Comprehensive error handling** with retry logic, isolation, and graceful degradation
- **Temporal workflow integration** with cloud deployment support (local, Temporal Cloud, custom servers)
- **Extensive test suite** with 344 tests covering unit, integration, vision analysis, haiku generation, and error scenarios
- **Modern Python tooling** with uv for dependency management and packaging

## Development Commands

### Environment Setup
```bash
uv sync --dev  # Install all dependencies including dev tools
```

### Running the Application
```bash
uv run around-the-grounds              # Run default site (ballard-food-trucks) (~60s)
uv run around-the-grounds --verbose    # Run with verbose logging (~60s)
uv run around-the-grounds --site park-slope-music   # Run a specific site
uv run around-the-grounds --site childrens-events   # Run another site
uv run around-the-grounds --site all                # Run all configured sites
uv run around-the-grounds --config /path/to/config.json  # Use custom config (~60s)
uv run around-the-grounds --preview    # Generate local preview files (~60s)
uv run around-the-grounds --deploy     # Run and deploy to GitHub Pages (~90s total)

# With AI features enabled (vision analysis + haiku generation)
export ANTHROPIC_API_KEY="your-api-key"
uv run around-the-grounds --verbose    # Run with AI features enabled (~60-90s)
uv run around-the-grounds --deploy     # Run with AI features and deploy to web (~90s)
```

**⏱️ Execution Times:** CLI operations typically take 60-90 seconds to scrape all venue websites concurrently. Add extra time for AI features (vision analysis, haiku generation) and git operations when using `--deploy`.

### Local Preview & Testing

Before deploying, generate and test web files locally:

```bash
# Generate web files locally for testing (~60s to scrape all sites)
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
# npm install -g puppeteer-cli
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
- Scrapes fresh data from all venue websites for the selected site
- Copies site-specific templates from `public_templates/<template>/` to `public/`
- Generates `data.json` with current event data
- Creates complete website in `public/` directory (git-ignored)

This allows you to test web interface changes, verify data accuracy, and debug issues before deploying to production.


### Web Deployment

**IMPORTANT**: Web deployment requires GitHub App authentication setup. See [DEPLOYMENT.MD](./DEPLOYMENT.MD) for configuration details.

```bash
# Deploy fresh data to GitHub Pages (full workflow)
uv run around-the-grounds --deploy

# Deploy a specific site
uv run around-the-grounds --site park-slope-music --deploy

# Deploy all sites
uv run around-the-grounds --site all --deploy

# Deploy to custom repository (overrides site config target_repo)
uv run around-the-grounds --deploy --git-repo https://github.com/username/repo.git

# This command will:
# 1. Scrape all venue websites for fresh event data
# 2. Copy site-specific templates from public_templates/<template>/ to target repo root
# 3. Generate web-friendly JSON data (data.json) in target repo root
# 4. Authenticate using GitHub App credentials
# 5. git init + force push complete website to target repository
# 6. GitHub Pages serves the site automatically
```

### Deployment
See [DEPLOYMENT.MD](./DEPLOYMENT.MD)

### Temporal Schedule Management
See [SCHEDULES.md](./SCHEDULES.md)

#### Schedule Features
- **Configurable intervals**: Any number of minutes (5, 30, 60, 120, etc.)
- **Multiple deployment modes**: Works with local, Temporal Cloud, and mTLS
- **Production ready**: Built-in error handling and detailed logging
- **Full lifecycle management**: Create, list, describe, pause, unpause, trigger, update, delete

### Testing
```bash
# Full test suite (344 tests)
uv run python -m pytest                    # Run all tests
uv run python -m pytest tests/unit/        # Unit tests only
uv run python -m pytest tests/parsers/     # Parser-specific tests
uv run python -m pytest tests/integration/ # Integration tests
uv run python -m pytest tests/unit/test_vision_analyzer.py  # Vision analysis tests
uv run python -m pytest tests/unit/test_haiku_generator.py  # Haiku generation tests
uv run python -m pytest tests/integration/test_vision_integration.py  # Vision integration tests
uv run python -m pytest tests/integration/test_haiku_integration.py   # Haiku integration tests
uv run python -m pytest tests/test_error_handling.py  # Error handling tests

# Test options
uv run python -m pytest -v                 # Verbose output
uv run python -m pytest --cov=around_the_grounds --cov-report=html  # Coverage
uv run python -m pytest -k "test_error"    # Run error-related tests
uv run python -m pytest -k "vision"        # Run vision-related tests
uv run python -m pytest -k "haiku"         # Run haiku-related tests
uv run python -m pytest -x                 # Stop on first failure
```

### Code Quality
```bash
uv run black .             # Format code
uv run isort .             # Sort imports
uv run flake8             # Lint code
uv run mypy around_the_grounds/  # Type checking
```

## Architecture

The project follows a modular architecture with clear separation of concerns:

```
around_the_grounds/
├── config/
│   ├── sites/                     # Per-site JSON configurations
│   │   ├── ballard-food-trucks.json   # Ballard food trucks (7 venues)
│   │   ├── park-slope-music.json      # Park Slope music venues (2 venues)
│   │   └── childrens-events.json      # Brooklyn children's events (2 venues)
│   ├── loader.py                  # Site config loader (load_site_config, load_all_sites)
│   ├── breweries.json             # Legacy venue list (used by Temporal activities)
│   ├── haiku_prompt.txt           # Haiku generation prompt template
│   └── settings.py                # Vision analysis and other settings
├── models/
│   ├── __init__.py                # Exports Venue, Event + backward-compat aliases
│   ├── brewery.py                 # Venue data model (renamed from Brewery)
│   ├── schedule.py                # Event data model (renamed from FoodTruckEvent)
│   └── site.py                    # SiteConfig data model
├── parsers/
│   ├── __init__.py                # Parser module exports
│   ├── base.py                    # Abstract base parser with error handling
│   ├── generic/                   # Platform-based generic parsers
│   │   ├── wordpress.py           # WordPressParser (REST API)
│   │   ├── html_selector.py       # HtmlSelectorParser (CSS selectors)
│   │   └── ajax.py                # AjaxParser (JSON API endpoints)
│   ├── stoup_ballard.py           # Stoup Brewing parser (venue-specific)
│   ├── bale_breaker.py            # Bale Breaker parser (venue-specific)
│   ├── urban_family.py            # Urban Family parser with vision analysis
│   └── registry.py                # Two-tier registry (venue-specific + generic)
├── scrapers/
│   └── coordinator.py             # Async scraping coordinator with error isolation
├── temporal/                      # Temporal workflow integration
│   ├── __init__.py                # Module initialization
│   ├── workflows.py               # FoodTruckWorkflow definition
│   ├── activities.py              # ScrapeActivities and DeploymentActivities
│   ├── config.py                  # Temporal client configuration system
│   ├── schedule_manager.py        # Comprehensive schedule management script
│   ├── shared.py                  # WorkflowParams and WorkflowResult data classes
│   ├── worker.py                  # Production-ready worker with error handling
│   ├── starter.py                 # CLI workflow execution client
│   └── README.md                  # Temporal-specific documentation
├── utils/
│   ├── date_utils.py              # Date/time utilities with validation
│   ├── github_auth.py             # GitHub App JWT authentication
│   ├── vision_analyzer.py         # AI vision analysis for vendor identification
│   └── haiku_generator.py         # AI haiku generation for food truck scenes
└── main.py                        # CLI entry point with multi-site and deployment support

public_templates/                  # Per-site web interface templates
├── food-trucks/                   # Ballard food trucks template
│   └── index.html
├── music/                         # Park Slope music template
│   └── index.html
└── kids/                          # Brooklyn children's events template
    └── index.html

public_template/                   # Legacy template directory (food-trucks)

public/                            # Generated files (git ignored)
└── data.json                      # Generated web data (not committed to source repo)

tests/                             # Comprehensive test suite (344 tests)
├── conftest.py                    # Shared test fixtures
├── fixtures/
│   ├── html/                      # Real HTML samples from venue websites
│   └── config/                    # Test configurations
├── unit/                          # Unit tests for individual components
├── parsers/                       # Parser-specific tests (including generic parsers)
├── integration/                   # End-to-end integration tests
├── temporal/                      # Temporal workflow tests
└── test_error_handling.py         # Comprehensive error scenario tests
```

### Key Components

- **Models**: Data classes for venues and events with validation
  - `Venue`: Represents a data source (was `Brewery`), includes `source_type` for parser selection
  - `Event`: Represents a single event (was `FoodTruckEvent`), includes `extraction_method`
  - `SiteConfig`: Represents a deployable site with venues, template, timezone, target repo
- **Parsers**: Two-tier parser system — venue-specific parsers take precedence, then generic platform parsers
  - `BaseParser`: Abstract base with HTTP error handling, validation, and logging
  - **Generic parsers** (config-driven, no code needed for new sites):
    - `WordPressParser`: Fetches events from WordPress REST API (`source_type: "wordpress"`)
    - `HtmlSelectorParser`: Extracts events via CSS selectors (`source_type: "html"`)
    - `AjaxParser`: Fetches from JSON API endpoints (`source_type: "ajax"`)
  - **Venue-specific parsers** (7 for Ballard food trucks): StoupBallard, BaleBreaker, UrbanFamily, etc.
- **Registry**: Two-tier lookup — by `venue.key` (specific) then by `venue.source_type` (generic)
- **Scrapers**: Async coordinator with concurrent processing, retry logic, and error isolation
- **Temporal**: Workflow orchestration for reliable execution and scheduling
- **Config**: Per-site JSON configs in `config/sites/`, loaded by `config/loader.py`
- **Utils**: Date/time utilities, AI vision analysis, AI haiku generation, GitHub App auth
- **Web Interface**: Per-site templates in `public_templates/<template>/` deployed to GitHub Pages
- **Web Deployment**: Git-based deployment (git init + force push) to per-site GitHub repos
- **Cloud Run**: Google Cloud Run Jobs with Cloud Scheduler for daily automated updates
- **Tests**: 344 tests covering all scenarios including generic parsers, error handling, vision analysis, and haiku generation

### Core Dependencies

**Production:**
- `aiohttp` - Async HTTP client for web scraping with timeout handling
- `beautifulsoup4` - HTML parsing with error tolerance
- `lxml` - Fast XML/HTML parser backend
- `requests` - HTTP library (legacy support)
- `anthropic` - Claude API for AI-powered image analysis and haiku generation
- `temporalio` - Temporal Python SDK for workflow orchestration

**Development & Testing:**
- `pytest` - Test framework with async support
- `pytest-asyncio` - Async test support
- `aioresponses` - HTTP response mocking for tests
- `pytest-mock` - Advanced mocking capabilities
- `freezegun` - Time mocking for date-sensitive tests
- `pytest-cov` - Code coverage reporting

The CLI is configured in `pyproject.toml` with entry point `around-the-grounds = "around_the_grounds.main:main"`.

## Adding New Sites and Venues

See [ADDING-VENUES.md](./ADDING-VENUES.md) for how to add new sites and venues using JSON config files and generic parsers.

## Haiku Generator

The system includes AI-powered haiku generation that creates contextual, poetic descriptions of daily food truck scenes. Haikus reflect the current season, feature specific food trucks and breweries, and follow traditional 5-7-5 syllable structure.

See [HAIKU-GENERATOR.md](./HAIKU-GENERATOR.md) for detailed documentation on configuration, usage, and implementation.

## AI Vision Analysis

The system includes AI-powered vision analysis to extract food truck vendor names from logos and images when text-based methods fail. The analyzer uses Claude Vision API as a fallback, with retry logic and graceful degradation.

See [VISION-ANALYSIS.md](./VISION-ANALYSIS.md) for detailed documentation on configuration, usage, and implementation.

## Error Handling Strategy

The application implements comprehensive error handling with error isolation, graceful degradation, and selective retry logic.

See [ERROR-HANDLING.md](./ERROR-HANDLING.md) for the complete error handling strategy guide.

## Code Standards

- **Line length**: 88 characters (Black formatting)
- **Type hints**: Required throughout (`mypy` with `disallow_untyped_defs = true`)
- **Python compatibility**: 3.8+ required
- **Import sorting**: Black profile via isort
- **Async patterns**: async/await for all I/O operations
- **Error handling**: Comprehensive error handling and logging required
- **Testing**: All new code must include unit tests and error scenario tests
- **Logging**: Use class loggers (`self.logger`) with appropriate levels

## Testing Strategy

The project includes a comprehensive test suite with 344 tests covering unit, integration, generic parsers, vision analysis, haiku generation, and error scenarios.

See [TESTING.md](./TESTING.md) for the complete testing strategy and guide.

## Development Workflow

When working on this project:

1. **Run tests first** to ensure current functionality works
2. **Write failing tests** for new features before implementation
3. **Implement with error handling** - always include try/catch and logging
4. **Test error scenarios** - network failures, invalid data, timeouts
5. **Preview changes locally** using `--preview` flag before deployment
6. **Run full test suite** before committing changes
7. **Update documentation** if adding new parsers or changing architecture

### Local Development Workflow
```bash
# 1. Make code changes
# 2. Test locally with preview
uv run around-the-grounds --preview
cd public && python -m http.server 8000

# 3. Run tests
uv run python -m pytest

# 4. Deploy when ready
uv run around-the-grounds --deploy
```

## Web Deployment Workflow

See [WEB-DEPLOYMENT.md](./WEB-DEPLOYMENT.md) for the complete web deployment workflow guide.

## Type Annotations

The project uses strict type checking with MyPy (`disallow_untyped_defs = true`) and Pylance.

See [TYPE-ANNOTATIONS.md](./TYPE-ANNOTATIONS.md) for the comprehensive type annotation maintenance guide.

## Troubleshooting Common Issues

- **Parser not found**: Check `parsers/registry.py` registration
- **Network timeouts**: Adjust timeout in `ScraperCoordinator` constructor
- **Date parsing issues**: Check `utils/date_utils.py` patterns and add new formats
- **Test failures**: Use `pytest -v -s` for detailed output and debug prints
- **Import errors**: Ensure `__init__.py` files are present and imports are correct