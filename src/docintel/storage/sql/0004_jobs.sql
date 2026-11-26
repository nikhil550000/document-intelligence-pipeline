-- The queue is this table: a worker takes a row with FOR UPDATE SKIP LOCKED, so
-- several workers take different rows without waiting for each other.
CREATE TABLE jobs (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    run_id uuid NOT NULL REFERENCES runs (id),
    document_id uuid NOT NULL REFERENCES documents (id),
    state text NOT NULL DEFAULT 'queued'
        CHECK (state IN ('queued', 'running', 'succeeded', 'failed')),
    -- Counted when the job is taken, so a job that kills its worker every time
    -- still runs out of attempts.
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    -- A job that failed waits until this time before it is taken again.
    available_at timestamptz NOT NULL DEFAULT now(),
    taken_at timestamptz,
    -- Past this time a running job's worker is taken to have died. Set by the
    -- worker that takes it, from the longest time its configuration allows.
    taken_until timestamptz CHECK (taken_until >= taken_at),
    failure_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz CHECK (finished_at >= created_at),
    UNIQUE (run_id, document_id),
    CHECK ((state = 'running') = (taken_at IS NOT NULL)),
    CHECK ((state = 'running') = (taken_until IS NOT NULL)),
    CHECK ((state = 'failed') = (failure_reason IS NOT NULL)),
    CHECK ((state IN ('succeeded', 'failed')) = (finished_at IS NOT NULL))
);

-- Ended jobs pile up run after run; these keep the two searches of the queue
-- to the few rows that are waiting or running.
CREATE INDEX jobs_queued ON jobs (id) WHERE state = 'queued';
CREATE INDEX jobs_running ON jobs (taken_until) WHERE state = 'running';

-- One row for each change of a job's state, written in the transaction of the
-- change. No foreign keys: a row must outlive the document it names.
CREATE TABLE audit_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    happened_at timestamptz NOT NULL DEFAULT now(),
    event text NOT NULL
        CHECK (event IN ('queued', 'started', 'queued_again', 'succeeded', 'failed')),
    job_id uuid NOT NULL,
    run_id uuid NOT NULL,
    document_id uuid NOT NULL,
    attempt integer NOT NULL CHECK (attempt >= 0),
    -- Why an attempt ended without an answer. No contract text goes here.
    reason text,
    CHECK ((event IN ('queued_again', 'failed')) = (reason IS NOT NULL))
);

CREATE FUNCTION refuse_audit_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit rows are never changed or removed';
END
$$;

CREATE TRIGGER audit_events_rows_stay
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION refuse_audit_change();

CREATE TRIGGER audit_events_table_stays
    BEFORE TRUNCATE ON audit_events
    FOR EACH STATEMENT EXECUTE FUNCTION refuse_audit_change();
