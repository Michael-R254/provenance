# 0006: Chat experience, recruiter mode and starter answers

- Status: accepted
- Date: 2026-11-25

## Context

The chat is the heart of the site. It must stream, show its evidence, explain itself, stay
accessible, cost nothing for common questions, and never let recruiter mode change facts.

## Decision

- **Plain `fetch` streaming.** `lib/api.ts` posts to `/v1/chat` and reads the body through a small
  incremental SSE parser (`lib/sse.ts`); `EventSource` cannot POST or send a bearer token. A
  stream that ends without `done` or `error` becomes an `unavailable` error, never a hang.
- **Sessions.** A Turnstile token (only when `NEXT_PUBLIC_TURNSTILE_SITE_KEY` is set) buys a
  session token, cached in `sessionStorage` until shortly before it expires. One automatic
  renewal on `invalid_session`.
- **Citations.** `[cN]` markers become numbered links to the cited section, named
  "Source N: title, section". Focus or hover highlights the matching evidence card. While a
  answer streams, chips resolve against the retrieved chunks; once `citations` arrives, only
  verified sources are used.
- **Evidence rail** beside the answer on wide screens; the same list in a bottom sheet on small
  screens. Excerpts come from `/v1/sources/{chunk_id}`.
- **Transparency drawer** per answer: method, index version, stage timings, every passage shown
  to the model with its scores and whether it was cited, removed citation IDs and uncited
  sentences. Nothing else from the server is shown; the API never sends prompts or settings.
- **Screen readers** hear one polite announcement per completed sentence (citation markers
  removed), then "Answer complete." The streaming text itself is `aria-busy`, not live.
- **Recruiter mode** (Just browsing, Recruiter, Hiring manager, Engineer) is stored in
  `localStorage` and changes only the starter questions and the project table order. The chat
  request type has no role field, and a Playwright test checks the request body.
- **Starter answers without a model call.** `content/starters.yaml` holds pre-written answers
  keyed by starter question id. Only entries with `status: approved` are used, and the build
  fails if an approved answer cites a section that is not on a published page. A starter without
  an approved answer is sent to the API like any other question.
- **States:** "waking" after 1.5 s without a `/health` reply (the page pings `/health` on load to
  wake a scaled-to-zero API), offline (checked before sending), rate-limited, spend cap,
  no-evidence with suggested topics, and generic errors with a retry button where retrying helps.
- **History** lives in `sessionStorage` for the tab; the last three answered turns are sent as
  context.

## Consequences

- Starter answers will be drafted from the live pipeline and reviewed by Michael before launch
  (M7); until then starters call the API.
- The chat panel appears on `/` and `/ask` (full screen, used on mobile and by "Ask about this
  project"). Other pages link to `/ask` from the header and command palette.
