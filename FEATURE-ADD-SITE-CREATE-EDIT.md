# Feature Plan: Site Authoring CLI (`feature/add-site-create-edit`)

## Purpose

Add a first-class CLI for site authoring inside ATG itself: inspect a URL,
create a site, edit an existing site, and lint site configs. This is the
implementation plan for the user-facing commands described in the product
specs `008-add-venues-to-site` and `009-create-new-sites`, and the draft
`REVISED-SITE-CONFIG-PLAN.md`.

This plan assumes the work lands upstream in ATG. A separate, later effort
will extract the same functionality into a sidecar application that works
against unmodified upstream ATG.

## Branch

- Base: `main`
- Name: `feature/add-site-create-edit`
- Reference implementation: `codex/lower-east-side-site-test` (code to port,
  not merge directly)

## Scope

In scope:

- `check-url` — inspect a URL and suggest a venue config
- `create-site` — create a new site config from validated inputs
- `edit-site` — repair an existing site config (`--show`, `--add-url`,
  `--remove-venue`, `--dry-run`)
- `site lint` — static validation of one or all site configs
- Shared HTTP headers used by both analyzer and runtime scraper
- `ParserRegistry.get_generic_parsers()` for registry-driven probing
- `parsers/generic/ajax.py` nested field paths and Afton endpoint defaults
- Tests and docs

Out of scope (explicit non-goals from `REVISED-SITE-CONFIG-PLAN.md`):

- Parser scaffolding / code generation
- AI-generated parser source code
- Runtime status stored in site config JSON
- Runtime tuning flags (`--max-concurrent`, `--timeout`)
- Auto-editing `ParserRegistry` imports

## Work-package breakdown

All five WPs land together in **one pull request**. Each WP is a single
coherent commit to keep the PR's history readable.

### WP01 — Upstream plumbing

Useful to ATG on its own merits; keeps the new CLI and the runtime scraper
consistent.

| Change | File |
|---|---|
| `default_request_headers()` | new `around_the_grounds/utils/http.py` |
| Switch scraper user agent to shared headers | `around_the_grounds/scrapers/coordinator.py` |
| `ParserRegistry.get_generic_parsers()` | `around_the_grounds/parsers/registry.py` |
| AJAX nested field paths, Afton endpoint defaults, `apiKey:` extraction | `around_the_grounds/parsers/generic/ajax.py` |
| Tests | `tests/unit/test_http_headers.py`, `tests/unit/test_registry.py`, `tests/parsers/test_ajax_parser.py` |

### WP02 — Config authoring primitives

Shared by create, edit, and lint. No CLI surface yet.

| Responsibility | File |
|---|---|
| Atomic write (`tempfile` + `os.replace`), create / add / remove venue helpers | new `around_the_grounds/config/writer.py` |
| `SiteConfigValidationError`, `validate_site_config`, `validate_site_key_unique`, template + timezone + target-repo + parser-resolution checks | new `around_the_grounds/config/validator.py` |
| Tests | new `tests/unit/test_config_writer.py`, `tests/unit/test_config_validator.py` |

### WP03 — URL analyzer

Probes a URL with every generic parser the registry exposes, ranks
attempts, and optionally falls back to Claude Haiku for HTML selector
suggestions.

- New `around_the_grounds/utils/url_analyzer.py` with `UrlAnalyzer`,
  `AnalysisResult`, and `StrategyAttempt` dataclasses
- Strategy ordering driven by `ParserRegistry.get_generic_parsers()` —
  no hardcoded generic parser imports
- AI fallback gated on `ANTHROPIC_API_KEY`, matching the existing
  `HaikuGenerator` / `VisionAnalyzer` graceful-degradation pattern
- Structured warnings: JavaScript app shells, Afton widget presence,
  missing start times, generic WordPress posts
- New `tests/unit/test_url_analyzer.py` with mocked `aiohttp` and
  `anthropic`

### WP04 — CLI restructure

Replace the string-match dispatch at the top of `main.main()` (used by
the codex branch) with proper argparse subparsers.

```
around-the-grounds                              # default: scrape (unchanged)
around-the-grounds --site NAME --deploy         # current flags still work
around-the-grounds check-url URL [URL...] [--source-type …] [--parser-config …] [--json]
around-the-grounds create-site --key … --name … --template … --timezone … --url … [--dry-run]
around-the-grounds edit-site KEY --show | --add-url URL | --remove-venue KEY [--dry-run]
around-the-grounds site lint [--site KEY]
```

Backward compatibility is a hard requirement — bare invocation and every
existing flag must continue to work so Cloud Run Jobs and the GitHub App
deploy flow do not break.

New modules:

- `around_the_grounds/cli/__init__.py`
- `around_the_grounds/cli/url_commands.py` (check-url)
- `around_the_grounds/cli/site_commands.py` (create-site + edit-site)
- `around_the_grounds/cli/lint_commands.py` (site lint)

`around_the_grounds/main.py` is refactored to route through a top-level
argparse subparser; `scrape` is the implicit default.

Tests:

- `tests/integration/test_check_url_cli.py`
- `tests/integration/test_create_site_cli.py`
- `tests/integration/test_edit_site_cli.py`
- `tests/integration/test_site_lint_cli.py`

### WP05 — Docs

- New `SITE-AUTHORING.md` at repo root covering all four commands
- Update `ADDING-VENUES.md` to recommend `create-site` / `edit-site`
  over hand-editing JSON
- Update `CLAUDE.md` dev commands and test section; bump the total test
  count
- Update `README.md` with a single-line mention if user-facing

## Design decisions for upstream acceptance

1. **argparse subparsers**, not the `if argv[0] == 'check-url'` shim used
   on the codex branch. Subparsers are the idiomatic pattern and integrate
   with the existing argparse in `main.py`.
2. **No hardcoded parser imports in the analyzer.** Probing is driven by
   `ParserRegistry.get_generic_parsers()`, so new generic parsers are
   auto-probed without code changes.
3. **AI is optional.** Missing `ANTHROPIC_API_KEY` skips AI fallback; it
   is not an error. Same pattern as `HaikuGenerator`.
4. **No new models.** Reuse `Venue`, `Event`, `SiteConfig`.
5. **Atomic writes.** Temp file plus `os.replace()`; no partial configs.
6. **Shared HTTP headers.** Analyzer and scraper use the same
   browser-like headers so the analyzer sees the same responses that the
   production scraper will later see.
7. **Scope guard.** No parser scaffolding, no AI parser generation, no
   runtime status in configs, no concurrency tuning flags.

## Intentionally dropped from the codex branch

- The `if args_list[0] == "check-url"` dispatch at the top of `main()`
- Whitespace-only reformatting unrelated to the feature

## Intentionally added beyond the codex branch

- `edit-site` command (all three sub-operations + `--dry-run`)
- `site lint` command
- Proper argparse subparser CLI structure
- Full doc set (WP05)

## Testing strategy

| Area | New tests |
|---|---|
| `utils/http.py` | ~5 |
| AJAX nested fields + Afton | ~8 |
| Registry `get_generic_parsers()` | ~3 |
| `config/writer.py` | ~15 |
| `config/validator.py` | ~15 |
| `utils/url_analyzer.py` | ~25 |
| `check-url` CLI | ~6 |
| `create-site` CLI | ~8 |
| `edit-site` CLI | ~10 |
| `site lint` CLI | ~6 |

Target is approximately **+100 tests**, bringing the suite from the
current 344 baseline to roughly 444. Existing tests must pass without
modification.

`mypy` must continue to pass with `disallow_untyped_defs = true`.

## Pull request strategy

**One pull request** targeting `main`, containing all five WPs as
separate commits for reviewability. Rationale: the CLI restructure
touches `main.py` and requires the new primitives from WP02 / WP03, so
splitting produces dependent PRs that cannot land independently.

## Acceptance criteria

- `uv run around-the-grounds` (no arguments) scrapes the default site,
  identical to today
- `uv run around-the-grounds --site <name> --deploy` behaves exactly as
  today (Cloud Run compatibility)
- `check-url URL` prints suggested `source_type` + `parser_config` +
  sample events, or "no events found"
- `create-site …` writes a valid JSON under `config/sites/` and refuses
  duplicate site keys
- `edit-site KEY --add-url URL` appends a venue with an analyzed
  parser config
- `edit-site KEY --remove-venue K` removes a venue and refuses unknown
  venue keys
- `edit-site KEY --show` pretty-prints the current config
- `site lint` catches missing template directories, invalid timezones,
  duplicate venue keys, unsupported source types, and filename / key
  mismatches
- All previous tests pass; new tests pass; `mypy` and `black` and
  `isort` all pass

## Relationship to existing specs

- `008-add-venues-to-site.md` — product spec for the "add venue"
  capability. This plan implements the CLI surface for it via
  `edit-site --add-url`.
- `009-create-new-sites.md` — product spec for the "new site"
  capability. This plan implements the CLI surface for it via
  `create-site`.
- `011-site-authoring-cli.md` — product spec paired with this plan,
  written in spec-kitty format for traceability.

## Follow-up (not in this PR)

- Sidecar application that provides the same authoring surface against
  unmodified upstream ATG. The analyzer reproduces
  `get_generic_parsers()` by reading `ParserRegistry._generic`
  directly, and the AJAX nested-field enhancement is replaced with
  either a PR to ATG or a local post-probe wrapper. That work is a
  separate effort and is explicitly out of scope here.
