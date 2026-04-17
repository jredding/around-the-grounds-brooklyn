# Site Authoring CLI

Around the Grounds ships four subcommands for inspecting URLs and
managing site configs without hand-editing JSON:

| Command | Purpose |
|---|---|
| `check-url` | Inspect a URL and suggest a venue config |
| `create-site` | Create a new site config from one or more URLs |
| `edit-site` | Repair an existing site config |
| `site lint` | Statically validate one or all site configs |

None of these commands change today's scrape / preview / deploy
workflows. Bare invocation (`uv run around-the-grounds ...`) and the
existing `--site`, `--config`, `--deploy`, `--preview`, `--git-repo`,
and `--verbose` flags continue to work exactly as before.

## check-url

```
uv run around-the-grounds check-url URL [URL ...]
                                    [--source-type TYPE]
                                    [--parser-config JSON]
                                    [--json]
```

Probes each URL against every generic parser the registry exposes
(`wordpress`, `ajax`, `html`, `json-ld`, ...), then optionally falls
back to a Claude Haiku HTML-selector suggestion when parser-based
analysis fails and `ANTHROPIC_API_KEY` is set.

### Output

Default is human-readable. `--json` emits a machine-readable object
per URL with every probed strategy, its confidence, and any warnings.

Common warnings:

- `Page appears to be a JavaScript-rendered app shell` — event data is
  rendered client-side; look for an API endpoint.
- `Page appears to embed an Afton Tickets widget` — the AJAX parser
  can auto-discover the `apiKey` and use the Afton feed.
- `Some events were found without start times.` — the parser works,
  but times are missing; `times_optional: true` is added to the
  suggested config.
- `Generic WordPress post parsing may need manual review.` — the
  probe fell back to `/wp-json/wp/v2/posts`; confidence is lowered.

### Directed testing

`--source-type` forces a single parser family; `--parser-config`
takes a JSON object that is used verbatim for the probe. Useful when
you already know the shape and only want to verify it:

```
uv run around-the-grounds check-url https://venue.com/events \
  --source-type ajax \
  --parser-config '{"api_url":"https://api.venue.com/events","response_path":"data"}'
```

### Exit codes

`0` when every URL produced a usable config; `1` otherwise. The
command never throws on zero-event results — those surface as
`message: "no events found"` with warnings.

## create-site

```
uv run around-the-grounds create-site \
  --key SITE_KEY --name "Display Name" \
  --template music --timezone America/New_York \
  --url URL [--url URL ...] \
  [--target-repo URL] [--generate-description] [--dry-run]
```

Runs `check-url` internally against each `--url`, validates the
generated config (template existence, timezone validity, venue key
uniqueness, parser resolution), then atomically writes
`around_the_grounds/config/sites/<key>.json`.

- `--target-repo` — GitHub Pages deploy target; defaults to empty.
- `--generate-description` — enables daily AI description for the
  site; off by default.
- `--dry-run` — prints the generated JSON without writing.
- `--key` — must be unique; command fails fast on collision with an
  existing `config/sites/<key>.json`.

All URLs must return events. If any URL returns `no events found`,
the command fails without writing, and hints for the failing URL
are printed so you can re-run `check-url` with directed flags.

## edit-site

```
uv run around-the-grounds edit-site SITE_KEY \
  ( --show | --add-url URL | --remove-venue VENUE_KEY ) \
  [--dry-run]
```

Exactly one operation per invocation.

- `--show` — pretty-prints the current site config.
- `--add-url URL` — runs the analyzer against the URL and appends the
  resulting venue. Fails on duplicate venue keys, no-events results,
  or analyzer errors. Use `--dry-run` to preview the merged config.
- `--remove-venue KEY` — removes a venue by its `key`. Fails if the
  venue does not exist. `--dry-run` previews.

Writes are atomic (temp file + `os.replace`), so interrupted edits
either fully succeed or leave the existing config untouched.

## site lint

```
uv run around-the-grounds site lint [--site SITE_KEY]
```

Runs static validation over every `config/sites/*.json` (or only the
named site). Suitable for CI. Catches:

- filename / key mismatch
- template directory missing
- invalid IANA timezone
- invalid `target_repo` URL shape
- duplicate venue keys within a site
- empty or malformed venue URLs
- unsupported `source_type` (checked against `ParserRegistry`)
- invalid JSON / missing required fields

Exit code is non-zero when any site fails. Success prints
`<site>.json: ok`; failures print one message per issue under the
site filename.

## Relationship to ADDING-VENUES.md

[ADDING-VENUES.md](./ADDING-VENUES.md) documents the underlying JSON
config shape and when a new venue needs a venue-specific parser. The
authoring CLI above is the recommended interface for the common
paths — only drop to hand-editing JSON when you need fine-grained
control over a `parser_config` that the analyzer cannot suggest on
its own.
