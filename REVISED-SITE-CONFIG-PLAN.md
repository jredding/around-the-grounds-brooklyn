# Revised Plan: Minimal Site Config Authoring and Repair

## Purpose

This is a reduced-scope replacement for the larger URL analysis and site config management plan. It keeps the work small, favors the site-based architecture already in the repo, and avoids features that introduce a lot of code or maintenance burden in the first iteration.

The goal for this iteration is simple:

1. Help a user inspect a URL and get a reasonable parser suggestion.
2. Help a user create a site config safely.
3. Help a user repair an existing site config when a venue changes.

This iteration is not trying to automate every edge case. It is trying to make the common workflow safer and faster with minimal code.

## Design Constraints

- Prefer small library modules over adding more logic to `around_the_grounds/main.py`.
- Keep existing scrape, preview, and deploy behavior unchanged.
- Do not add parser scaffolding in this iteration.
- Do not add runtime tuning flags like `--max-concurrent` or `--timeout`.
- Do not store runtime status in site config JSON.
- Shared fetch behavior must be realistic enough for public venue pages that block bare or scraper-like HTTP clients.
- Treat stress testing as a way to discover missing product features, not just validate the new commands.

## Scope

### In Scope

- `check-url`
- site config write/update helpers
- `create-site`
- `edit-site` with a narrow set of operations
- lightweight config validation

### Out of Scope

- `create-parser`
- AI-generated parser code
- deep parser internals diagnostics
- auto-editing `ParserRegistry` imports
- runtime status persistence in site configs

## Proposed Commands

### `check-url`

Purpose: inspect a URL and suggest the most likely ATG config shape.

Example:

```bash
uv run around-the-grounds check-url URL [URL...]
uv run around-the-grounds check-url URL --source-type wordpress --parser-config '{"api_path":"/wp-json/tribe/events/v1/events"}'
uv run around-the-grounds check-url URL --json
```

Behavior:

- Default output is human-readable.
- `--json` returns machine-readable results.
- `--source-type` and `--parser-config` allow directed testing of a known parser path.
- Parser attempts must come from the current ATG parser collection, not a separately maintained hardcoded list.
- Returns:
  - suggested `source_type`
  - suggested `parser_config`
  - confidence
  - sample events when available
  - warnings when detection is weak or no events were found
  - `no events found` when all attempts fail

Important behavior:

- `check-url` should first try parser-based analysis using the generic parser collection derived from `ParserRegistry`.
- If parser-based analysis does not produce event data, it may reuse existing AI-based analysis capabilities already present in ATG.
- If all attempts fail, the result should be `no events found`.
- Zero events must not automatically mean failure.
- Missing start times must not automatically mean failure.
- The tool should distinguish:
  - parser likely valid, but no current events
  - parser likely invalid
  - ambiguous result

### `create-site`

Purpose: create a new site config from validated venue inputs.

Example:

```bash
uv run around-the-grounds create-site --key KEY --name NAME --template TEMPLATE --timezone TZ --url URL --url URL
```

Behavior:

- Runs `check-url` internally unless `--source-type` and `--parser-config` are explicitly provided for all URLs.
- Writes `around_the_grounds/config/sites/{key}.json`.
- Fails on duplicate site key.
- Fails on duplicate venue keys in the new site.
- Fails when a required URL returns `no events found`.
- Validates template and timezone before writing.
- Supports `--dry-run` to show the generated config without saving.

### `edit-site`

Purpose: repair and maintain an existing site config.

Example:

```bash
uv run around-the-grounds edit-site KEY --show
uv run around-the-grounds edit-site KEY --add-url URL
uv run around-the-grounds edit-site KEY --remove-venue VENUE_KEY
```

Behavior for this iteration:

- `--show`
  - pretty-print current config
  - show only config facts: venue key, source type, URL, template, timezone
- `--add-url`
  - analyze and append a new venue
- `--remove-venue`
  - remove one or more venues by key
- `--dry-run`
  - show the resulting config without saving

Not included in this iteration:

- `--update-venue`
- `--reanalyze`
- `--diagnose`
- last-known status output
- verbose parser trace output

### `site lint`

Purpose: catch config problems before runtime.

Example:

```bash
uv run around-the-grounds site lint
uv run around-the-grounds site lint --site KEY
```

Behavior:

- Validates all sites or one site.
- Checks:
  - site key exists and matches file name
  - template directory exists
  - timezone is valid
  - venue keys are unique within a site
  - parser source type is supported
  - JSON shape is valid
  - target repo format is sane if present

This is intentionally static validation only.

## Library Modules

### `around_the_grounds/config/writer.py`

Responsibilities:

- save site config atomically
- create site config
- add venues
- remove a venue

Requirements:

- output JSON must match current site config structure
- write through temp file plus `os.replace()`
- no behavior tied to runtime scrape state

### `around_the_grounds/config/validator.py`

Responsibilities:

- validate `SiteConfig`
- validate template existence
- validate timezone
- validate duplicate keys
- validate source types against `ParserRegistry`

This should be reusable by `create-site`, `edit-site`, and `site lint`.

### `around_the_grounds/utils/url_analyzer.py`

Base this on the existing `feature/analyze-url` work, but reduce and reshape it.

Required changes:

- do not hardcode generic parser imports as the long-term interface
- use `ParserRegistry` as the source of supported generic parser types
- preserve room for known-site heuristics where generic detection is not enough
- derive parser attempts from the registry-backed parser collection so new generic parser support is picked up automatically
- use shared browser-like request headers for analyzer fetches so live venue pages are fetched consistently across analyzer and scrape paths
- reuse existing AI-based analysis capabilities already present in ATG as a fallback path rather than introducing a separate unsupported-source result
- return structured warnings, not just success/failure

Detection model for this iteration:

1. known heuristics for parser families already present in ATG
2. generic parser probes derived from `ParserRegistry`
3. existing AI-based analysis fallback when parser attempts do not produce event data
4. confidence and warnings

The analyzer should not pretend that generic parsing is enough for every `html` site.
The final user-facing failure state should remain simple: `no events found`.

## Parser Strategy Principles

- Known venue-specific patterns should be acknowledged when recognized.
- Generic parser suggestions should be conservative.
- The parser attempt set must stay aligned with the codebase dynamically through `ParserRegistry`, not through duplicated explicit imports.
- AI fallback is a secondary path after parser attempts, not a separate product mode.
- Confidence should drop when:
  - no events are found
  - multiple strategies partially match
  - date extraction works but time extraction does not
  - the parser only succeeds with very generic selectors

## CLI Integration

Keep the current scrape flow in place.

Add a small command-routing layer so `main.py` dispatches to dedicated handlers instead of owning all logic directly.

Suggested shape:

- `around_the_grounds/cli/site_commands.py`
- `around_the_grounds/cli/url_commands.py`

`main.py` should only parse args and route to those handlers.

## Stress Testing for Feature Discovery

The purpose of stress testing in this planning phase is to identify missing product features or workflow gaps.

### Scenarios to Run

1. Analyze a valid venue with zero upcoming events.
   Possible feature learned:
   - draft or unverified venue state
   - softer language in analysis output

2. Analyze a venue that publishes dates but not times.
   Possible feature learned:
   - explicit support for time-optional venues in analysis UX

3. Add two venues from the same domain.
   Possible feature learned:
   - better key generation or explicit `--venue-key`

4. Run `check-url` against a venue after a site redesign.
   Possible feature learned:
   - a future convenience wrapper that reapplies analysis results to a saved site
   - confidence diff or change summary in `check-url`

5. Show a large site config with many venues.
   Possible feature learned:
   - compact table output
   - warnings-only view

6. Create a site with mixed parser families.
   Possible feature learned:
   - stronger normalization of generated config formatting

7. Analyze a social URL such as Instagram alongside normal venue pages.
   Possible feature learned:
   - whether the existing AI analysis fallback is sufficient
   - whether a later blacklist or explicit unsupported-source behavior is worth adding

8. Analyze a known tricky source that currently needs a specific parser.
   Possible feature learned:
   - explicit "generic parser not recommended" warning

These scenarios are not mainly about proving the commands work. They are about revealing what the next smallest useful features should be.

## Implementation Order

1. Add `ParserRegistry.get_generic_parsers()`.
2. Add `config/writer.py`.
3. Add `config/validator.py`.
4. Import and reduce the analyzer from `feature/analyze-url`.
5. Add `check-url`.
6. Add `create-site`.
7. Add `edit-site` with `--show`, `--add-url`, and `--remove-venue`.
8. Add `site lint`.

## Testing Plan

### Unit Tests

- registry generic parser access
- config write round-trip
- atomic write behavior
- duplicate venue detection
- invalid template detection
- invalid timezone detection
- shared HTTP header defaults
- URL analyzer confidence and warning behavior
- URL analyzer behavior when zero events are found
- URL analyzer behavior when times are missing

### Integration Tests

- `check-url` human output
- `check-url --json`
- `create-site --dry-run`
- `create-site` writes a valid config
- `edit-site --show`
- `edit-site --add-url`
- `edit-site --remove-venue`
- `site lint`

### Live Validation Findings

Dry-run testing against a real Lower East Side example exposed an implementation requirement that should stay in the plan:

- `https://www.caveat.nyc/` is a JavaScript app shell, but it exposes a usable event feed at `/api/events/listings`.
- `https://www.arlenesgrocerynyc.com/upcoming-events` embeds a live Afton widget and does have event data.
- The failure mode was not missing events. The failure mode was that bare `aiohttp` requests received `403` while browser-like requests succeeded.
- Shared browser-like headers are therefore part of the real implementation, not an optional enhancement.
- Validation of new site creation should continue to use `--dry-run` first when testing real sites so we prove detection without writing config files.

## Acceptance Criteria

- A user can inspect a URL and get a suggested config without reading parser code.
- A user can create a site config safely with minimal manual JSON editing.
- A user can repair one venue in an existing site without hand-editing the whole config.
- Static config errors are caught before scrape or preview.
- The implementation adds minimal new code and avoids parser scaffolding or deep diagnostics.

## Explicit Deferrals

These can become later iterations if stress testing proves they are worth it:

- parser scaffolding
- AI-assisted parser generation
- deep live diagnostics
- parser trace mode
- runtime tuning flags
- status history for venues

## Lobakgo Scope

Lobakgo should remain a thin web UI for ATG, not a second implementation of ATG logic.

### Separation Requirements

The following responsibilities should live in ATG, not lobakgo:

- source detection
- site config building
- site config validation
- site generation

Lobakgo should call ATG-backed endpoints for these operations and only render the results needed by the user.

### Minimal Lobakgo Product Shape

The create page should remain a simple single-page flow:

- enter title, contact, and source URLs
- submit once to create
- show simple parse and create feedback from ATG

The edit page should be the main maintenance surface for an existing site:

- add URLs
- remove URLs
- reanalyze or reparse URLs
- change visual style
- change timezone
- change slug
- update contact
- delete page

URL reordering does not need backend work and is not part of this plan.

### Lobakgo Features to Avoid in This Iteration

Do not expand lobakgo into a larger product surface for this work. Specifically avoid:

- multi-step creation wizards
- dedicated URL review screens
- config diff screens
- separate lint dashboards
- source health dashboards
- generation status dashboards
- parser management features

The intent is to keep lobakgo simple while ATG becomes the source of truth for site authoring and maintenance logic.
