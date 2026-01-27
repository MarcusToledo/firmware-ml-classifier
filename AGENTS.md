# Agent Operating Guide (AGENTS.md)

This repository is a TCC project on automated firmware classification
using static analysis and supervised ML. The guidance below is for
agentic coding assistants operating in this repo.

## Project Scope (Immutable)
- Static firmware analysis only (no dynamic execution).
- Supervised vendor/manufacturer classification only.
- Hybrid features:
  - Statistical: size, entropy, byte distribution, compressibility.
  - Semantic: ASCII strings + Doc2Vec embeddings (DM or DBOW).
- Models:
  - Extra Trees as the main model.
  - Random Forest as the baseline.
- Avoid heavy deep learning due to small datasets.
- All changes must be academically justified and reproducible.

## Agent Responsibilities
- dataset-agent
  - Curate, sample, and version datasets under `dataset/`.
  - Preserve labels and provenance metadata.
- feature-agent
  - Implement statistical and string-based feature extraction in `src/`.
  - Keep feature code modular and auditable.
- doc2vec-agent
  - Train Doc2Vec only on strings from the local dataset.
  - Save model and embeddings; document hyperparameters.
- model-agent
  - Train, tune, and evaluate Extra Trees and Random Forest.
  - Avoid scope creep into unrelated model families.
- evaluation-agent
  - Produce reproducible metrics, confusion matrices, and reports.
  - Store outputs under `reports/`.
- reproducibility-agent
  - Enforce fixed seeds, deterministic pipelines, and artifact tracking.

## Build, Lint, Test
- Install dependencies:
  - `python -m pip install -r requirements.txt`
- Run all tests:
  - `python -m pytest`
- Run a single test:
  - `python -m pytest tests/path::test_name`
- Run tests with verbose output:
  - `python -m pytest -vv`
- Lint (if adopted):
  - `python -m ruff check .`
- Format (if adopted):
  - `python -m black .`
- Type check (if adopted):
  - `python -m mypy src`
- Keep pytest as the mandatory test runner.

## Pipeline Commands (Placeholders)
- Build dataset:
  - `python scripts/build_dataset.py`
- Sample dataset:
  - `python scripts/sample_dataset.py`
- Train models:
  - `python scripts/train.py`

## Code Style Guidelines
- Imports:
  - Order: standard library, third-party, local modules.
  - Prefer explicit imports over wildcard imports.
  - Group imports with a blank line between groups.
- Formatting:
  - 4-space indentation.
  - Default line length target: 88 characters.
  - Keep functions focused and under ~60 lines when possible.
  - Use consistent blank lines between logical blocks.
  - Avoid trailing whitespace; keep a newline at EOF.
  - Prefer early returns to reduce nesting.
- Types:
  - Add type hints to all public functions and class methods.
  - Use `Path` for filesystem paths in public APIs.
  - Type dataset I/O clearly (paths, arrays, DataFrames).
  - Use `Optional` only when `None` is expected and handled.
- Naming:
  - snake_case for modules, functions, and variables.
  - PascalCase for classes.
  - UPPER_CASE for constants.
  - Use descriptive names for features and model artifacts.
- Error handling:
  - Validate inputs early; raise informative exceptions.
  - Fail fast on corrupt binaries or invalid labels.
  - Avoid silent fallbacks that hide data quality issues.
  - Include context in exceptions (file, vendor, stage).
- Logging:
  - Use the `logging` module for pipeline steps.
  - Include dataset size, feature counts, and model parameters.
  - Log deterministic seeds and dataset splits.
- File I/O and safety:
  - Treat firmware binaries as untrusted input.
  - Use safe, defensive reads and size checks.
  - Do not assume file encodings beyond ASCII for strings.
- Reproducibility:
  - Fix random seeds for NumPy/sklearn and document them.
  - Persist trained models and embeddings under `models/`.
  - Persist datasets under `dataset/processed/` with metadata.
  - Store experiment outputs under `reports/` with timestamps.
- Data boundaries:
  - No data leakage between train/validation/test splits.
  - Document sampling procedures in scripts.
  - Keep label maps stable across runs.

## Doc2Vec Requirements
- Each firmware is a single document.
- Store Doc2Vec parameters (vector size, window, epochs, min_count).
- Save:
  - Trained model file.
  - Embedding vectors aligned to firmware IDs.
- Do not mix external embeddings unless justified in writing.

## Scientific Integrity
- Do not invent experimental results.
- Do not expand scope beyond firmware classification.
- Prefer simple, explainable approaches over opaque automation.
- Minimize external dependencies; avoid internet reliance.
- Maintain traceability for all datasets and models.

## Repository Structure (Target)
- `dataset/`
  - `raw/` for original firmware binaries organized by vendor.
  - `interim/` for sampled or intermediate subsets.
  - `processed/` for final feature tables.
- `src/`
  - `features/` (statistical, strings, doc2vec).
  - `io_utils.py`, `text_utils.py`.
- `scripts/`
  - `build_dataset.py`, `train.py`, `sample_dataset.py`.
- `models/` for trained model artifacts.
- `reports/` for metrics and figures.

## TODO Tracking
- Keep `TODO.md` updated for each request.
- List completed and pending points on every update.
- Use short, actionable checklist items.

## Cursor/Copilot Rules
- No Cursor rules detected (`.cursor/rules/`, `.cursorrules`).
- No Copilot rules detected (`.github/copilot-instructions.md`).

## Operational Boundaries
- Keep the project aligned with the TCC goals.
- Document decisions and justify changes academically.
- Never generate or claim empirical results without execution.
- Keep the repository organized and auditable.
- Avoid hidden automation or non-deterministic steps.
- Respond in pt-br only; allow English only for technical terms.
