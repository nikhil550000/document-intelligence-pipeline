-- The text of a document as one version of one parser read it. Another parser,
-- or a newer version of this one, adds a row next to it and replaces nothing.

CREATE TABLE parsed_texts (
    document_id uuid NOT NULL REFERENCES documents (id),
    parser text NOT NULL,
    parser_version text NOT NULL,
    -- The pages, a JSON list of strings, are in object storage under this hash.
    text_sha256 text NOT NULL CHECK (text_sha256 ~ '^[0-9a-f]{64}$'),
    parse_seconds double precision NOT NULL CHECK (parse_seconds >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, parser, parser_version)
);
