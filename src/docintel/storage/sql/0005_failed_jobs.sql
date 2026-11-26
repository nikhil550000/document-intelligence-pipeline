-- A contract whose job ends failed is stored as failed by the queue, so the
-- report still counts it. A job given up because its worker died has no
-- request the queue could know, so a failed extraction may have none.
ALTER TABLE extractions
    ALTER COLUMN request_sha256 DROP NOT NULL,
    ADD CONSTRAINT extractions_request_check
        CHECK (status = 'failed' OR request_sha256 IS NOT NULL);
