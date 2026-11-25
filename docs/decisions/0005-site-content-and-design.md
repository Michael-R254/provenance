# 0005: Site pages from content, anchors and the Field Console design system

- Status: accepted
- Date: 2026-11-25

## Context

Project pages must show exactly what the guide can cite, link targets must match citation
anchors, drafts must never leak, and the site must work without JavaScript and score well on
mobile.

## Decision

- **Pages are generated at build time from `content/`** by `apps/web/src/lib/content.ts`. It
  returns only `status: approved` files, rejects malformed approved files (bad type, slug or
  file name, invalid YAML) instead of guessing, and sorts by `updated`. The folder can be
  overridden with `PROVENANCE_CONTENT_DIR`; tests and screenshots always use the fictional
  corpus in `evals/fixtures/content`.
- **Draft guard after every build.** `scripts/check-no-drafts.mjs` runs as `postbuild` and fails
  the build if the id or title of any unapproved file appears anywhere in `.next`.
- **Anchors match ingestion.** `lib/anchors.ts` mirrors `ingest/anchors.py`; both run the shared
  vectors in `ingest/tests/fixtures/anchor-vectors.json`. Only `##` headings get ids; the title
  takes the first anchor (text before the first `##`), as in ADR 0002.
- **Markdown is rendered safely**: remark, GFM, then rehype with raw HTML dropped and output
  sanitised; `#` headings are removed (the page has its own `h1`).
- **Design tokens** are CSS variables mapped into Tailwind: paper light theme, deep-moss dark
  theme, one moss accent, amber reserved for warnings. The system theme applies without
  JavaScript; a saved choice is applied by a tiny inline script before paint. Controls that need
  JavaScript (search, theme, table filter) carry `js-only` and are hidden when it is off.
- **Fonts are self-hosted** from `@fontsource` packages via `next/font/local`, Latin subset only:
  Newsreader (variable), IBM Plex Sans 400/600, IBM Plex Mono 400.
- **Motion** is CSS transitions only for now; `prefers-reduced-motion` sets durations to zero.
  The Motion library arrives with the chat panel if it is needed there.

## Consequences

- Cache Components needs at least one static param, so with no published projects a placeholder
  slug is generated and renders the not-found page.
- An unknown or unpublished slug returns the not-found page with `noindex` but HTTP 200, because
  the shell streams before the page decides. No draft text is ever served (tested).
- Lighthouse mobile on the fixture project page: performance 96, accessibility 100, best
  practices 100.
