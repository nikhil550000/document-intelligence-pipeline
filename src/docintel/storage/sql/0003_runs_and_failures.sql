-- A run knows which contracts it was given, how much it may spend, and how it
-- ended. No run has been stored yet, so the new columns need no default.
ALTER TABLE runs
    ADD COLUMN contract_list text NOT NULL,
    ADD COLUMN cost_ceiling_usd numeric(12, 6) NOT NULL CHECK (cost_ceiling_usd >= 0),
    -- complete: every contract ended, answered or failed. stopped: the ceiling
    -- was reached first. running: still going, or the process died.
    ADD COLUMN status text NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'complete', 'stopped')),
    ADD COLUMN stop_reason text,
    ADD CONSTRAINT runs_stop_reason_check
        CHECK ((status = 'stopped') = (stop_reason IS NOT NULL));

-- An output that does not load into the record type has no record, but it is
-- kept: its response is in object storage and its problems are listed.
ALTER TABLE extractions
    DROP CONSTRAINT extractions_check,
    ADD CONSTRAINT extractions_record_check CHECK (
        (status = 'failed' AND record IS NULL)
        OR (status = 'needs_review')
        OR (status IN ('valid', 'repaired') AND record IS NOT NULL)
    ),
    -- The request's hash is the cache key: the same model, prompt, contract and
    -- settings give the same hash, and a stored answer is used again for free.
    ADD COLUMN request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
    -- The response as the provider sent it. A failed call has none.
    ADD COLUMN response_sha256 text CHECK (response_sha256 ~ '^[0-9a-f]{64}$'),
    ADD COLUMN cached_input_tokens integer NOT NULL
        CHECK (cached_input_tokens >= 0 AND cached_input_tokens <= input_tokens),
    -- Taken from an earlier run's response, so no call was made and nothing paid.
    ADD COLUMN from_cache boolean NOT NULL,
    ADD CONSTRAINT extractions_response_check
        CHECK ((status = 'failed') = (response_sha256 IS NULL));

CREATE INDEX extractions_request_sha256 ON extractions (request_sha256)
    WHERE response_sha256 IS NOT NULL;

CREATE TABLE validation_issues (
    extraction_id bigint NOT NULL REFERENCES extractions (id) ON DELETE CASCADE,
    -- The order the check found them in, which also keys the row.
    position integer NOT NULL CHECK (position >= 0),
    layer text NOT NULL,
    rule text NOT NULL,
    -- Null when the problem is the output as a whole, such as broken JSON.
    field_name text,
    message text NOT NULL,
    PRIMARY KEY (extraction_id, position)
);
