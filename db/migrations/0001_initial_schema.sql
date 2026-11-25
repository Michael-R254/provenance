-- 0001: initial schema. See docs/architecture.md section 5.

CREATE EXTENSION IF NOT EXISTS vector;

-- One row per ingestion run. Exactly one row may be active at a time.
CREATE TABLE index_versions (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    git_sha          text,
    embedding_model  text NOT NULL,
    chunker_version  text NOT NULL,
    status           text NOT NULL DEFAULT 'building'
                     CHECK (status IN ('building', 'active', 'retired', 'failed')),
    created_at       timestamptz NOT NULL DEFAULT now(),
    activated_at     timestamptz
);
CREATE UNIQUE INDEX index_versions_one_active ON index_versions ((true)) WHERE status = 'active';

CREATE TABLE projects (
    index_version  bigint NOT NULL REFERENCES index_versions (id) ON DELETE CASCADE,
    slug           text NOT NULL,
    title          text NOT NULL,
    summary        text NOT NULL,
    type           text NOT NULL,
    period         text,
    repo_url       text,
    tags           jsonb NOT NULL DEFAULT '{}'::jsonb,
    guardrails     jsonb NOT NULL DEFAULT '[]'::jsonb,
    PRIMARY KEY (index_version, slug)
);

CREATE TABLE documents (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    index_version  bigint NOT NULL REFERENCES index_versions (id) ON DELETE CASCADE,
    project_slug   text,
    title          text NOT NULL,
    doc_type       text NOT NULL CHECK (doc_type IN ('project', 'profile')),
    source_path    text NOT NULL,
    url            text NOT NULL,
    version        integer NOT NULL,
    content_hash   text NOT NULL,
    UNIQUE (index_version, source_path)
);
CREATE INDEX documents_index_version ON documents (index_version);

CREATE TABLE chunks (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    index_version  bigint NOT NULL REFERENCES index_versions (id) ON DELETE CASCADE,
    document_id    bigint NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    section        text NOT NULL,
    anchor         text NOT NULL,
    ordinal        integer NOT NULL,
    text           text NOT NULL,
    token_count    integer NOT NULL,
    embedding      vector(384) NOT NULL,
    tsv            tsvector GENERATED ALWAYS AS (
                       to_tsvector('english', section || ' ' || text)
                   ) STORED,
    UNIQUE (document_id, ordinal)
);
CREATE INDEX chunks_index_version ON chunks (index_version);
CREATE INDEX chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_tsv_gin ON chunks USING gin (tsv);

-- Knowledge graph (populated in M8).
CREATE TABLE entities (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    index_version  bigint NOT NULL REFERENCES index_versions (id) ON DELETE CASCADE,
    kind           text NOT NULL
                   CHECK (kind IN ('project', 'skill', 'language', 'framework', 'model', 'research_area')),
    label          text NOT NULL,
    UNIQUE (index_version, kind, label)
);

CREATE TABLE entity_links (
    source_id          bigint NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    target_id          bigint NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    relation           text NOT NULL,
    evidence_chunk_id  bigint NOT NULL REFERENCES chunks (id) ON DELETE CASCADE,
    PRIMARY KEY (source_id, target_id, relation)
);

-- Operations (written by the API from M3).
CREATE TABLE query_logs (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id        text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    question          text NOT NULL,
    retrieved         jsonb NOT NULL DEFAULT '[]'::jsonb,
    answer_status     text NOT NULL,
    model             text,
    tokens_in         integer NOT NULL DEFAULT 0,
    tokens_out        integer NOT NULL DEFAULT 0,
    cost_usd          numeric(10, 6) NOT NULL DEFAULT 0,
    stage_timings_ms  jsonb NOT NULL DEFAULT '{}'::jsonb,
    citations_valid   boolean
);
CREATE INDEX query_logs_created_at ON query_logs (created_at);

CREATE TABLE rate_limits (
    key           text NOT NULL,
    window_start  timestamptz NOT NULL,
    count         integer NOT NULL DEFAULT 0,
    PRIMARY KEY (key, window_start)
);

CREATE TABLE eval_runs (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    git_sha          text,
    model            text,
    dataset_version  text NOT NULL,
    metrics          jsonb NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now()
);
