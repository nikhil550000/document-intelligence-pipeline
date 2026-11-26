-- A worker takes a run's jobs only if it was built from the same code, so what
-- a run records is what did the work. Older runs have no hash, and no worker
-- takes them.
ALTER TABLE runs
    ADD COLUMN code_sha256 text CHECK (code_sha256 ~ '^[0-9a-f]{64}$');
