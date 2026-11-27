-- Whether the run's traces carry the contracts' text and the model's answers,
-- so it is known afterwards what was sent to the tracing tool. Older runs sent
-- no traces at all.
ALTER TABLE runs
    ADD COLUMN trace_contract_text boolean NOT NULL DEFAULT false;
