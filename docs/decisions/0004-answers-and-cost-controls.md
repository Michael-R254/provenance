# 0004: Answer generation, citation checks and cost controls

- Status: accepted
- Date: 2026-11-25

## Context

Answers must be grounded in Michael's approved write-ups, cite them, never leak the prompt, and
never run up a bill. The live model is Claude Haiku 5.5, chosen for cost.

## Decision

- **One provider interface** (`LLMProvider.stream` yields text, then one `GenerationResult`).
  `AnthropicProvider` uses the official SDK with the fixed system prompt marked for prompt
  caching and extended thinking turned off (short grounded answers do not need it and it adds
  output cost). `OllamaProvider` is free local development. `MockProvider` is the default and the
  only provider used in tests. Production settings refuse to start with anything but the
  Anthropic provider and real secrets.
- **Prompt in one versioned file** (`prompts/answer-v1.md`). Evidence, guardrails and the
  question go in the user turn inside tagged sections; text that tries to close those sections
  is stripped. Recruiter role is not a field of the chat request, so it cannot reach the prompt.
- **Citations are checked while streaming.** `CitationFilter` holds back at most a few characters
  after `[` until it can tell whether a marker is a known ID; unknown IDs never reach the visitor
  and are listed in the `citations` event. Sentences without a citation are reported, not hidden
  (a semantic support check is wave 2).
- **Evidence threshold on vector similarity only.** Any-term keyword matching (ADR 0003) finds
  something for nearly every question, so it cannot signal that evidence exists. The 0.35 value is
  a placeholder until real content and the real embedder are evaluated.
- **Follow-up rewrite is rule-based.** A model call would cost money and could be steered by
  injected text; joining a short or pronoun-led question to the previous one is enough for
  retrieval. Revisit with real questions.
- **Cost controls in the API** (on top of prepaid credit with auto-reload off):
  - Daily spend cap from today's `query_logs.cost_usd` (UTC). Checked before retrieval, then
    again with the worst-case cost of this answer (`estimate_max_cost_usd`: generous input
    estimate plus `max_output_tokens`), so the cap cannot be crossed by one large answer.
  - Turnstile before a session token; HMAC-signed tokens that expire after an hour.
  - Fixed-window rate limits in Postgres per session (minute and day) and per IP hash (hour,
    and session issuing per hour). IPs are hashed with a secret salt and the date, never stored,
    and rows older than 24 hours are deleted.
  - Limits on question length, history turns and characters, and `max_output_tokens`.
- **Errors are generic.** Visitors see an error code and a friendly message; details go to logs.
  The OpenAPI schema is off in production.

## Consequences

- Concurrent requests near the cap can overshoot it by a few answers' worth (well under a cent
  each with Haiku). The prepaid credit remains the hard ceiling.
- Rate-limit and spend checks add two small queries per question; acceptable at portfolio scale.
- `/v1/sources` and `/v1/projects` have no rate limit of their own; Cloud Run `max-instances`
  bounds them. Revisit if they are abused.
