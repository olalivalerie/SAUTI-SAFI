-- Optional manual repair for an existing PostgreSQL Phase 3 database.
-- The application also performs these migrations automatically at startup.

CREATE TABLE IF NOT EXISTS monitoring_topics (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    name VARCHAR(120) NOT NULL,
    query VARCHAR(512) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_monitoring_topic_user_name ON monitoring_topics(user_id, name);

ALTER TABLE posts ADD COLUMN IF NOT EXISTS topic_id INTEGER REFERENCES monitoring_topics(id);
ALTER TABLE posts ADD COLUMN IF NOT EXISTS author_username VARCHAR(255);
ALTER TABLE posts ADD COLUMN IF NOT EXISTS author_id VARCHAR(255);
ALTER TABLE posts ADD COLUMN IF NOT EXISTS language VARCHAR(20);
ALTER TABLE posts ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS post_id INTEGER REFERENCES posts(id);
