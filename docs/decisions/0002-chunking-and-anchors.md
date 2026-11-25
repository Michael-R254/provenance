# 0002: Chunking, anchors and index versions

- Status: accepted
- Date: 2026-11-25

## Context

Citations must link to the exact place on a project page, retrieval must work on short,
focused passages, and a bad content change must never break the live guide.

## Decision

**Chunking (chunker version 1).**
- One chunk per `##` section of a content file. Text before the first `##` is filed under the
  document title. `#` headings are dropped; `###` and deeper stay inside their section.
- Headings inside fenced code blocks are ignored. HTML comments are removed.
- Sections longer than 300 words are split on paragraph boundaries; each piece repeats the
  previous piece's last paragraph as overlap (unless that paragraph is itself long). A single
  paragraph over the limit is kept whole rather than cut mid-sentence.
- The embedded text is `"{document title} | {section}\n\n{chunk text}"`, so each vector carries
  its context. `token_count` is an estimate (4 tokens per 3 words) for budgeting only.

**Anchors (shared with the web app).** GitHub-style: lowercase; remove every character that is
not a letter, digit, space, hyphen or underscore; replace each space with a hyphen; repeated
anchors in one document get `-1`, `-2`, ... The web app (M4) must produce identical heading ids,
and a shared test fixture will check both sides agree.

**Content rules.** Only `content/projects/*.md` (projects) and top-level `content/*.md` (profile
documents) are read; files starting with `_` and README files are ignored. A project's file name
must equal its `id`. Unknown frontmatter keys are errors. Drafts are skipped; any other status
is an error. An approved project cannot have `permission: pending`.

**Index versions.** Each run writes a complete new version (`building`) in one transaction.
Activation retires the previous active version in one transaction; a partial unique index
guarantees at most one active version. Rollback is `python -m ingest activate <id>`.

## Consequences

- Changing chunking or the embedding model means bumping `CHUNKER_VERSION` or the model name
  and re-indexing; old versions stay queryable until retired.
- The API (M2) must check that the active version's `embedding_model` matches the model it uses
  for queries, so a version built with the test embedder can never serve real traffic.
