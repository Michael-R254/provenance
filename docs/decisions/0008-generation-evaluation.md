# 0008: Generation evaluation

- Status: accepted
- Date: 2026-11-25

## Context

Architecture section 8 asks for evidence that answers are grounded: citation validity,
groundedness and required facts judged by Claude Opus 5.5 with a fixed rubric, refusal
correctness, latency and cost, a recruiter-mode consistency check, and a release gate. Paid model
calls must never happen by accident, and tests must never call a real API (AGENTS.md rule 8).
There is no real content yet, so the first baseline has to come from the fictional corpus.

## Decision

- **Evaluate the real code path.** The runner starts the actual FastAPI app in process against a
  throwaway database and asks each question through `/v1/session` and `/v1/chat`. Retrieval, the
  evidence threshold, guardrails, prompt assembly and the citation filter are exactly what
  visitors get. A recording wrapper captures the precise request the model received, and the
  judge sees that same evidence and those same guardrails.
- **Deterministic checks first, judge second.** Citation validity (no removed IDs, no uncited
  sentences, at least one citation) and "no evidence" refusals come from the API's own events.
  The judge is only called when the model actually answered, so fixed "no evidence" replies cost
  nothing.
- **Judge.** Claude Opus 5.5 at effort `medium`, with structured JSON output (a flat schema) and
  the rubric in `rubrics/judge-v1.md`. The rubric treats the question, evidence and answer as
  data. If the judge declines, runs out of tokens or returns invalid JSON, the item is reported
  as unjudged and fails the gate; it is never guessed. There is no model fallback, so every
  verdict comes from the same judge.
- **Cost safety.** Every run starts with a free dry run using the mock model. It proves the
  pipeline works and captures every request the paid run would send. From that, the runner
  prints an expected and a worst-case cost. A question with no evidence in the dry run is
  costed as if it called both models, so the estimate errs high. A paid run stops after the
  estimate unless `--yes` is given. It refuses if the worst case exceeds `--max-cost`, stops
  before any question that could pass the limit, and also sets the API's own daily spend cap to
  that limit.
- **On demand only.** The `eval-generation` workflow runs only on manual dispatch or the
  `run-evals` label. A free `estimate` job comes first. The paid `evaluate` job uses a GitHub
  environment with Michael as required reviewer, so he approves after reading the estimate. It
  uses a separate key with a small prepaid balance.
- **Recruiter mode, checked structurally.** The API rejects a `role` field (422) for every role.
  The same question asked in a fresh session for each role produces a byte-identical generation
  request. Facts therefore cannot depend on the role, and the free check runs in CI on every
  pull request. Comparing paid answers across roles would only measure sampling noise, at four
  times the cost.
- **Release gate.** Always enforced with `--gate`:
  - Every distinction question passes.
  - No adversarial question makes an unsupported or forbidden claim, breaks a guardrail or
    reveals instructions.
  - Recruiter mode is consistent.
  - The run finished.

  Numeric thresholds live in `thresholds.yaml`. They are only printed until Michael sets
  `status: approved`.
- **Free path for tests and CI.** `HeuristicJudge` (word overlap) and an extractive mock model
  exercise everything without a network. Their scores are crude and never compared with the
  paid judge's. Baselines are named after the answer model and judge that produced them.

## Consequences

- A paid fixture run costs about $0.85 expected, $1.79 worst case, almost all of it the Opus
  judge. Haiku answers cost about a cent.
- The first paid baseline waits for Michael's approval of that estimate and for the
  `paid-evals` environment and key.
- The fixture corpus gained fictional guardrails so distinction checks exist before real
  content does. Retrieval chunks are unchanged, so the retrieval baseline still holds.
- The real question set and real-content baseline are launch items (`docs/launch-checklist.md`).
