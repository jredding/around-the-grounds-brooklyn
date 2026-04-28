# Backlog

Potential future work, not yet committed to. Each entry should capture enough context to be picked up later without re-deriving the design.

---

## Expose `venue_url` in `data.json`

**Goal:** Let templates render event titles as clickable links to the venue's events/calendar page (the "origination source"), so users can navigate to ticket pages or more detail.

**Why it's not done now:** Requires a small change to upstream (`around_the_grounds/main.py:generate_web_data`) which is jointly maintained with `steveandroulakis/around-the-grounds`. Held back to keep the Brooklyn fork's surface area minimal and avoid drift from upstream until we decide to PR it.

**Proposed change (one field, additive):**

In `generate_web_data`, alongside the existing `web_event` fields, add:

```python
"venue_url": next(
    (v.url for v in site.venues if v.key == event.venue_key), None
) if site else None,
```

Templates then read `event.venue_url` and wrap the title in `<a href="${event.venue_url}">…</a>` when present. Affected templates: `public_templates/music/index.html`, `public_templates/kids/index.html`. Ballard's `food-trucks` template can opt in or ignore the new field.

**Properties:**
- Additive only — new field, no existing field changes, no template breakage.
- Generic — benefits any site, not Brooklyn-specific. Good candidate to PR upstream.
- Lossy vs. per-event URLs — links to the venue's calendar page, not the specific event's ticket page. Per-event URLs would require a `url` field on `Event` and parser-by-parser extraction (much larger change).

**Rejected alternatives:**
- Per-event `Event.url` + parser changes — too invasive (~10 parsers + model + tests).
- Hardcoded `venue → URL` map duplicated in each template's JS — works without upstream changes but duplicates data already in site configs and silently rots when venue URLs change.
