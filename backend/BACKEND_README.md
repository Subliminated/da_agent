# backend/

Short description

This folder contains the main API and business logic for ingestion, parsing, orchestration and job management. The backend validates uploads, persists raw files and parsed datasets, coordinates LLM planning, and dispatches execution jobs to the sandbox.

Primary responsibilities

- Accept and validate uploads (`POST /api/v1/datasets/upload`).
- Parse `csv`/`xlsx` into canonical tabular formats (parquet/json).
- Persist raw uploads and parsed outputs under `backend/storage/`.
- Provide dataset and job APIs (datasets, previews, analysis jobs).
- Orchestrate LLM interactions and validate model plans before execution.
- Submit isolated jobs to the sandbox runner and collect artifacts/logs.
- Enforce security/allowlists and redact sensitive data before logging.

Key layout (examples)

- `app/api/v1/` — HTTP routes and controllers
- `app/domain/` — Dataset, AnalysisJob, ExecutionResult models
- `services/parsing/`, `services/storage/`, `services/sandbox/`, `services/llm/`
- `storage/` — `raw_uploads/`, `parsed_datasets/`, `job_artifacts/`
- `tests/` — unit and integration tests

Notes

- Use structured JSON logging and propagate `X-Request-ID`/trace headers.
- Keep execution out of process — use workers/queue to submit sandbox jobs.
- Recommended stack: Python + FastAPI + Pydantic + pandas/polars (or Node.js equivalent).
