-- Ids that leave the database (in the API and in logs) are time-ordered UUIDs, so
-- they cannot be guessed and still index like a growing number.

CREATE TABLE documents (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    -- The PDF is stored in object storage under this hash.
    sha256 text NOT NULL UNIQUE CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    file_name text NOT NULL,
    byte_size bigint NOT NULL CHECK (byte_size > 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE runs (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    config_name text NOT NULL,
    -- The whole configuration is kept, so a run can be repeated after the file changes.
    config jsonb NOT NULL,
    git_commit text NOT NULL CHECK (git_commit ~ '^[0-9a-f]{40}$'),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz CHECK (finished_at >= started_at)
);

CREATE TABLE extractions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES runs (id),
    document_id uuid NOT NULL REFERENCES documents (id),
    status text NOT NULL
        CHECK (status IN ('valid', 'repaired', 'needs_review', 'failed')),
    record jsonb,
    failure_reason text,
    model text NOT NULL,
    prompt_version text NOT NULL,
    schema_version text NOT NULL,
    input_tokens integer NOT NULL CHECK (input_tokens >= 0),
    output_tokens integer NOT NULL CHECK (output_tokens >= 0),
    cost_usd numeric(12, 6) NOT NULL CHECK (cost_usd >= 0),
    -- A stage that was never reached has no time.
    parse_seconds double precision CHECK (parse_seconds >= 0),
    extract_seconds double precision CHECK (extract_seconds >= 0),
    total_seconds double precision NOT NULL CHECK (total_seconds >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, document_id),
    -- A record that fails its checks is still stored; only a failed call has none.
    CHECK ((status = 'failed') = (record IS NULL)),
    CHECK ((status = 'failed') = (failure_reason IS NOT NULL))
);

-- Postgres does not index a foreign key by itself, and documents are looked up
-- by their extractions.
CREATE INDEX extractions_document_id ON extractions (document_id);

-- One row per field, with the answer in the column of its type, so that a query
-- such as "expires before a date" is a plain comparison. All value columns null
-- means the contract does not say.
CREATE TABLE field_values (
    extraction_id bigint NOT NULL REFERENCES extractions (id) ON DELETE CASCADE,
    field_name text NOT NULL,
    present boolean,
    date_value date,
    perpetual boolean,
    duration_amount integer,
    duration_unit text CHECK (duration_unit IN ('days', 'months', 'years')),
    text_value text,
    party_names text[],
    evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'array'),
    PRIMARY KEY (extraction_id, field_name),
    CHECK ((duration_amount IS NULL) = (duration_unit IS NULL)),
    CHECK (NOT (perpetual AND date_value IS NOT NULL))
);

-- CUAD's answers. Kept as JSON because a field can have several accepted values,
-- and only the scorer reads them.
CREATE TABLE gold_values (
    document_id uuid NOT NULL REFERENCES documents (id),
    field_name text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('value', 'none', 'skipped')),
    skip_rule text,
    accepted_values jsonb CHECK (jsonb_typeof(accepted_values) = 'array'),
    PRIMARY KEY (document_id, field_name),
    CHECK ((kind = 'skipped') = (skip_rule IS NOT NULL)),
    CHECK ((kind = 'value') = (accepted_values IS NOT NULL))
);

-- Counts and not one outcome, because parties are scored name by name.
CREATE TABLE scores (
    extraction_id bigint NOT NULL REFERENCES extractions (id) ON DELETE CASCADE,
    field_name text NOT NULL,
    true_positives integer NOT NULL CHECK (true_positives >= 0),
    false_positives integer NOT NULL CHECK (false_positives >= 0),
    false_negatives integer NOT NULL CHECK (false_negatives >= 0),
    skip_rule text,
    PRIMARY KEY (extraction_id, field_name),
    CHECK (
        skip_rule IS NULL
        OR (true_positives = 0 AND false_positives = 0 AND false_negatives = 0)
    )
);
