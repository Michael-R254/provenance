-- Least-privilege role for the public API (AGENTS.md rule 5: read the active index, write logs).
-- Run once in the Neon SQL editor as the owner, after the first migration, then put this role's
-- connection string in Secret Manager as provenance-api-database-url. Choose the password in
-- the Neon console; never commit it.
--
--   CREATE ROLE provenance_api LOGIN PASSWORD '<set in the Neon console>';
--
-- Then run the grants below. They are safe to re-run after new migrations.

GRANT USAGE ON SCHEMA public TO provenance_api;

-- Corpus: read only. Only the ingest workflow (owner role) writes these.
GRANT SELECT ON index_versions, projects, documents, chunks, entities, entity_links
    TO provenance_api;

-- Logs: insert answers, read today's spend for the daily cap. No update or delete.
GRANT SELECT, INSERT ON query_logs TO provenance_api;

-- Rate limits: fixed windows are counted and old windows pruned.
GRANT SELECT, INSERT, UPDATE, DELETE ON rate_limits TO provenance_api;
