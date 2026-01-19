# TODO

## Request: Create/Improve AGENTS.md and establish TODO tracking

### Completed
- [x] Review existing `AGENTS.md` and `README.md` for current guidance and commands.
- [x] Update `AGENTS.md` with build/lint/test commands, code style guidelines, and TODO tracking rules.
- [x] Confirm no Cursor/Copilot rules are present and document that in `AGENTS.md`.

### Pending
- [ ] None.

## Request: Add pt-br only response rule

### Completed
- [x] Add rule requiring pt-br responses with only technical English terms in `AGENTS.md`.

### Pending
- [ ] None.

## Request: Feature extraction skeleton

### Completed
- [x] Create feature extraction modules and functions for static features and Doc2Vec.
- [x] Add unit tests with pytest for statistics, strings, and io_utils.
- [x] Update string extraction with max_string_len and normalization.
- [x] Expand string extraction tests for limits and normalization.
- [x] Add compressibility level validation and logging.
- [x] Mark truncation when string or document limits apply.
- [x] Seed Doc2Vec inference for deterministic embeddings.
- [x] Reuse strings_to_document in feature extraction.
- [x] Add YAML-based pipeline config with overrides.
- [x] Add CLI entry for batch feature extraction.
- [x] Add pipeline tests for config, extraction, and CLI.
- [x] Add Doc2Vec unit tests with realistic tokens and determinism checks.

### Pending
- [ ] Adjust default limits (`max_strings`, `max_doc_chars`) after dataset profiling.
