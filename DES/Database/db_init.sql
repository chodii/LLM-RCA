DROP INDEX log_chunks_source_chunk_idx;
DROP INDEX log_chunks_start_time_idx;
DROP INDEX log_chunks_end_time_idx;
DROP INDEX log_chunks_content_text_trgm_idx;
DROP TABLE log_chunks;


CREATE TABLE log_chunks (
    id BIGSERIAL PRIMARY KEY,
    source_path TEXT NOT NULL,
    chunk_id INTEGER NOT NULL,
    
    content_json JSONB NOT NULL,
    content_text TEXT NOT NULL,

    time_start TIMESTAMPTZ NULL,
    time_end TIMESTAMPTZ NULL,
    has_time BOOLEAN NOT NULL DEFAULT TRUE,
    
    CHECK ((has_time = FALSE) OR (has_time = TRUE AND time_start <= time_end)),

    UNIQUE (source_path, chunk_id)
);

CREATE INDEX log_chunks_source_chunk_idx
    ON log_chunks (source_path, chunk_id);

CREATE INDEX log_chunks_start_time_idx
    ON log_chunks (time_start);

CREATE INDEX log_chunks_end_time_idx
    ON log_chunks (time_end);


CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX log_chunks_content_text_trgm_idx
    ON log_chunks
    USING GIN (content_text gin_trgm_ops);
