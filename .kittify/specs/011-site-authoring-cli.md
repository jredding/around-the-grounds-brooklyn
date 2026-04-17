# Feature Specification: Site Authoring CLI

**Feature Branch**: `feature/add-site-create-edit`
**Created**: 2026-04-17
**Status**: Draft
**Input**: User description: "Add first-class CLI commands to ATG for inspecting a URL, creating a site, editing an existing site, and linting site configs. Implements the user-facing surface for specs 008 (add venues) and 009 (create sites)."

## User Scenarios & Testing

### User Story 1 - Inspect a URL and get a parser suggestion (Priority: P1)

A site operator has a candidate venue URL and wants to know whether ATG's generic parsers can extract events from it before committing the venue to a site config.

**Why this priority**: Today the operator has to hand-author a venue JSON entry and run a full scrape to find out whether the source works. This is the most common friction point when onboarding a new venue.

**Independent Test**: Run `uv run around-the-grounds check-url https://www.caveat.nyc/`, verify the tool reports a usable `source_type` and `parser_config`, plus sample events.

**Acceptance Scenarios**:

1. **Given** a URL backed by an AJAX event API, **When** the operator runs `check-url URL`, **Then** the tool prints the suggested `source_type`, `parser_config`, confidence, sample events, and any warnings.
2. **Given** a URL with no extractable events, **When** `check-url` runs, **Then** the output says `no events found` and lists attempted strategies plus hints.
3. **Given** a URL that returns dates but no times, **When** `check-url` runs, **Then** the tool succeeds with a warning that times are missing, not failure.
4. **Given** a JavaScript app shell, **When** `check-url` runs, **Then** the output warns the page appears to be a JS app shell and event data may require API-specific parsing.
5. **Given** `--json` is passed, **When** `check-url` runs, **Then** the output is valid JSON suitable for piping.

---

### User Story 2 - Create a new site from validated URLs (Priority: P1)

A site operator creates a new site by providing a site key, display name, template, timezone, and one or more source URLs. The tool analyzes each URL, validates the resulting config, and writes it atomically.

**Why this priority**: Spec 009 describes the capability; without a CLI the operator still has to hand-edit JSON. This command is the direct user-facing surface.

**Independent Test**: Run `create-site --key les-test --name "LES Test" --template music --timezone America/New_York --url https://www.caveat.nyc/ --dry-run`, verify the generated JSON matches the on-disk schema.

**Acceptance Scenarios**:

1. **Given** valid inputs and URLs that each return events, **When** `create-site` runs, **Then** a new `config/sites/<key>.json` is written atomically with the analyzed venue configs.
2. **Given** a site key that already exists, **When** `create-site` runs, **Then** the command fails with a clear duplicate-key error before any analysis.
3. **Given** one URL that returns `no events found`, **When** `create-site` runs, **Then** the command fails and names the offending URL.
4. **Given** `--dry-run`, **When** `create-site` runs, **Then** the generated JSON is printed and no file is written.
5. **Given** an unknown template or invalid timezone, **When** `create-site` runs, **Then** the command fails validation before writing.

---

### User Story 3 - Repair an existing site by adding or removing a venue (Priority: P1)

A site operator maintains an existing site config by adding a new venue URL or removing a venue that has moved or gone offline, without hand-editing JSON.

**Why this priority**: Real-world site maintenance is the most frequent operation after initial creation. Edit operations directly enable the workflow described in spec 008.

**Independent Test**: Run `edit-site park-slope-music --add-url https://example.com/events`, verify the venue is appended with an analyzed parser config. Then run `edit-site park-slope-music --remove-venue example-com` and verify it is removed.

**Acceptance Scenarios**:

1. **Given** an existing site config, **When** `edit-site KEY --show` runs, **Then** the current config is pretty-printed with venue key, source type, URL, template, and timezone.
2. **Given** an existing site and a new URL, **When** `edit-site KEY --add-url URL` runs, **Then** the URL is analyzed and appended as a new venue in `config/sites/<key>.json`.
3. **Given** an existing site, **When** `edit-site KEY --remove-venue VENUE_KEY` runs, **Then** the venue is removed from the config.
4. **Given** a venue key that does not exist, **When** `--remove-venue` runs, **Then** the command fails with a clear error.
5. **Given** `--dry-run`, **When** any edit operation runs, **Then** the resulting config is printed and no file is written.
6. **Given** a URL passed to `--add-url` that returns no events, **When** the command runs, **Then** it fails without modifying the config.

---

### User Story 4 - Lint site configs statically (Priority: P2)

A site operator runs a static validation pass against one or all site configs to catch configuration errors before scrape or preview.

**Why this priority**: Preventive validation. The existing `--preview` flow catches errors but requires a full scrape; lint gives fast feedback and is suitable for CI.

**Independent Test**: Introduce a typo in a site's `timezone`, run `site lint --site <key>`, verify the error is caught and the command exits non-zero.

**Acceptance Scenarios**:

1. **Given** a valid site config, **When** `site lint --site KEY` runs, **Then** the command exits 0 with no errors.
2. **Given** all site configs are valid, **When** `site lint` runs (no `--site`), **Then** every config is validated and the command exits 0.
3. **Given** a config whose filename does not match its `key`, **When** lint runs, **Then** the mismatch is reported.
4. **Given** a config that references a non-existent template directory, **When** lint runs, **Then** the missing template is reported.
5. **Given** a config with an invalid IANA timezone, **When** lint runs, **Then** the invalid timezone is reported.
6. **Given** a config with duplicate venue keys, **When** lint runs, **Then** each duplicate is reported.
7. **Given** a venue whose `source_type` is not supported by `ParserRegistry`, **When** lint runs, **Then** the unsupported source type is reported.

---

### Edge Cases

- A source URL is behind a bot filter that rejects bare HTTP clients with 403. The analyzer uses the same browser-like headers as the production scraper, so the analyzer sees what the scraper will later see.
- A source returns events but no start times. This is a warning, not a failure. `times_optional` is added to `parser_config`.
- A source returns zero current events but is otherwise a valid target. The analyzer distinguishes "parser likely valid, no current events" from "parser likely invalid" via warnings; the command exits successfully but labels confidence accordingly.
- Two venues share a hostname. Auto-generated venue keys collide; operators resolve with an explicit venue-key-override in a later iteration. For this iteration the tool fails with a duplicate-key error.
- `create-site` is interrupted mid-write. Atomic `tempfile` + `os.replace()` ensures the destination file is either unchanged or fully replaced; no half-written JSON.
- `ANTHROPIC_API_KEY` is not set. AI fallback is skipped; the analyzer returns whatever parser-based result it has, including `no events found` if nothing matched.

## Requirements

### Functional Requirements

- **FR-001**: System MUST expose `check-url`, `create-site`, `edit-site`, and `site lint` as argparse subcommands of `around-the-grounds`.
- **FR-002**: System MUST preserve today's bare `around-the-grounds` invocation (scrape default site) and all current flags unchanged.
- **FR-003**: `check-url` MUST probe a URL against every generic parser exposed by `ParserRegistry.get_generic_parsers()`, in a stable priority order.
- **FR-004**: `check-url` MUST support directed testing via `--source-type` and `--parser-config` JSON.
- **FR-005**: `check-url` MUST support `--json` for machine-readable output.
- **FR-006**: `check-url` MUST distinguish "parser likely valid, no events" from "parser likely invalid" via warnings and confidence, not via binary success.
- **FR-007**: `check-url` MUST fall back to AI-based HTML selector suggestion when parser-based analysis fails and `ANTHROPIC_API_KEY` is set; absence of the key MUST NOT be an error.
- **FR-008**: `create-site` MUST validate template existence, timezone validity, duplicate site keys, and duplicate venue keys before writing.
- **FR-009**: `create-site` MUST write `config/sites/<key>.json` atomically via temp-file plus `os.replace()`.
- **FR-010**: `create-site --dry-run` MUST print the generated JSON without writing any file.
- **FR-011**: `edit-site --show` MUST pretty-print the current config.
- **FR-012**: `edit-site --add-url URL` MUST analyze the URL and append the resulting venue entry to the existing config.
- **FR-013**: `edit-site --remove-venue KEY` MUST remove the venue and fail if the key does not exist.
- **FR-014**: `edit-site --dry-run` MUST print the resulting config without writing.
- **FR-015**: `site lint` MUST validate: site-key uniqueness, filename / key match, template directory existence, timezone validity, venue-key uniqueness, `source_type` resolution via `ParserRegistry`, and basic `target_repo` URL shape.
- **FR-016**: Site config writes MUST match the existing on-disk JSON shape (`key`, `name`, `template`, `timezone`, `target_repo`, `generate_description`, `venues[]`).
- **FR-017**: Analyzer HTTP fetches and production scraper HTTP fetches MUST share a common set of browser-like request headers via `around_the_grounds/utils/http.py`.
- **FR-018**: `ParserRegistry` MUST expose `get_generic_parsers()` so the analyzer can iterate the generic-parser map without importing generic parser classes directly.
- **FR-019**: The generic `AjaxParser` MUST support nested field paths in `field_map` (e.g., `fields.Event`) so analyzer-suggested configs against real APIs parse correctly at runtime.

### Key Entities

- **`UrlAnalyzer`**: New class in `around_the_grounds/utils/url_analyzer.py`. Probes URLs, returns `AnalysisResult`.
- **`AnalysisResult`**: Dataclass with `url`, `success`, `venue_config`, `confidence`, `warnings`, `sample_events`, `attempts`, `message`.
- **`StrategyAttempt`**: Per-strategy outcome with `strategy`, `source_type`, `applied`, `events_found`, `valid_events`, `timed_events`, `confidence`, `parser_config`, `sample_events`, `warnings`, `error`.
- **`SiteConfigValidationError`**: New exception in `around_the_grounds/config/validator.py`.
- **`around_the_grounds/config/writer.py`**: Module-level helpers `save_site_config`, `create_site_config`, `add_venues_to_site`, `remove_venue_from_site`.
- **`around_the_grounds/cli/`**: New package containing `url_commands.py`, `site_commands.py`, `lint_commands.py`.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Bare `around-the-grounds` invocation and existing `--site`, `--deploy`, `--preview`, `--config`, `--git-repo`, `--verbose` flags behave identically to today (verified by existing tests passing unchanged).
- **SC-002**: `check-url` against a known-good venue from each generic parser family (wordpress, ajax, html) returns `success=True` with a non-empty `sample_events` list.
- **SC-003**: `create-site --dry-run` against the same inputs used on the codex branch (Lower East Side venues) produces a JSON structure byte-identical to the codex branch's output after normalization.
- **SC-004**: `edit-site KEY --add-url URL` followed by `edit-site KEY --remove-venue KEY` leaves the config byte-identical to the starting state.
- **SC-005**: `site lint` catches every failure listed in FR-015 and exits non-zero.
- **SC-006**: Full test suite passes. New tests add roughly 100 cases across writer, validator, analyzer, and CLI surfaces.
- **SC-007**: `mypy` continues to pass with `disallow_untyped_defs = true`.
- **SC-008**: Cloud Run Jobs continue to succeed without configuration changes after this feature lands.
