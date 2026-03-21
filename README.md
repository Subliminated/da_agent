# Data Analyst Agent

Starter repository structure and development guide for a data analyst agent with:

- a separate web frontend
- a separate backend API
- upload-first data ingestion
- structured parsing for `csv` and `xlsx`
- LLM-driven analysis orchestration
- a separate Docker-based execution boundary for safe code execution

This repository is intentionally scaffolded first. It gives you a clean place to build the app without prematurely locking in implementation details.

## Product Goal

The application flow is:

1. A user must upload a data source first.
2. The backend validates the file type and ingests the file.
3. The backend parses the file into a structured internal representation.
4. The parsed dataset is stored separately from the raw upload.
5. The user can then ask analysis questions against that parsed dataset.
6. The LLM decides what operation should be run.
7. Execution happens in a separate, isolated Docker environment against the approved dataset snapshot.
8. Results are returned to the backend and then to the frontend.

Current assumptions:

- only `csv` and `xlsx` uploads are supported
- uploaded data is already cleaned and structured
- Excel is the primary working format after ingestion
- execution must not run inside the main API/web container or host process

## Recommended Architecture

Use a monorepo with clear service boundaries:

- `frontend/`
  The web application. Handles upload UX, dataset browsing, job status, and result rendering.
- `backend/`
  The main API. Handles authentication later, upload validation, parsing, dataset metadata, LLM orchestration, and dispatching jobs to the sandbox runner.
- `docker/sandbox/`
  Build context for the isolated execution environment. This should contain the Dockerfile and runner logic used for safe data operations.
- `shared/`
  Shared contracts such as JSON schemas, API types, and dataset/result payload definitions.
- `docs/`
  Optional deeper architecture notes beyond this README.

The key design rule is:

`frontend` never touches files directly after upload, and `backend` never executes arbitrary analysis code in-process.

## Repository Structure

```text
data_analyst_agent/
├── .github/
│   └── workflows/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       └── routes/
│   │   ├── core/
│   │   ├── domain/
│   │   │   ├── analysis/
│   │   │   ├── datasets/
│   │   │   ├── execution/
│   │   │   └── parsing/
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── llm/
│   │   │   ├── parsing/
│   │   │   ├── sandbox/
│   │   │   └── storage/
│   │   └── workers/
│   ├── storage/
│   │   ├── job_artifacts/
│   │   ├── parsed_datasets/
│   │   └── raw_uploads/
│   └── tests/
│       ├── integration/
│       └── unit/
├── docker/
│   └── sandbox/
├── docs/
│   ├── api/
│   └── architecture/
├── frontend/
│   ├── public/
│   └── src/
│       ├── app/
│       ├── components/
│       ├── features/
│       │   ├── datasets/
│       │   └── upload/
│       └── lib/
├── shared/
│   └── contracts/
└── README.md
```

## What Each Area Should Own

### `frontend/`

Recommended responsibility:

- dataset upload page
- dataset list/detail views
- parsing status display
- analyst chat or query interface
- job execution history
- result tables and chart rendering

Recommended internal modules:

- `src/features/upload/`
  Upload form, file validation UX, progress UI
- `src/features/datasets/`
  Dataset browsing and detail pages
- `src/lib/`
  API client, shared utilities, typed response helpers

Suggested stack:

- Next.js or React + Vite
- TypeScript
- TanStack Query for API state
- a table library for dataset previews

### `backend/`

Recommended responsibility:

- accept uploads
- validate mime type and extension
- generate dataset IDs
- persist raw files
- parse `csv` and `xlsx`
- normalize into a structured schema
- store parsed outputs and metadata
- expose dataset/query APIs
- call the LLM for planning
- dispatch approved operations to the sandbox runner
- collect results and logs

Suggested internal separation:

- `api/`
  HTTP routes and controllers only
- `domain/`
  Core business concepts like datasets, parsing jobs, analysis jobs, execution policies
- `services/storage/`
  Raw file storage, parsed file storage, artifact storage
- `services/parsing/`
  CSV/XLSX loaders and normalization logic
- `services/llm/`
  Prompting, tool decision logic, guardrails
- `services/sandbox/`
  Docker job submission, mount rules, timeouts, output collection
- `schemas/`
  Request/response DTOs and validation models

Suggested stack:

- Python with FastAPI or Node.js with NestJS/Express
- Pydantic/Zod for validation
- pandas or polars for parsing and structured export

If you want the simplest path for tabular data work, Python backend is the stronger default.

### `docker/sandbox/`

This is the isolated execution environment for data operations requested by the LLM.

It should eventually contain:

- a `Dockerfile`
- a minimal runner entrypoint
- only approved analysis libraries
- strict CPU, memory, network, and execution-time limits
- a read-only mounted dataset input when possible
- a writable output directory for results only

The sandbox container should not:

- hold app secrets
- have direct database credentials
- have unrestricted network access
- mount the entire repository

### `shared/contracts/`

Use this for definitions that both frontend and backend need to agree on, such as:

- dataset metadata shape
- parsed dataset summary shape
- job status enums
- execution result payloads

If frontend and backend are in different languages, keep shared contracts as JSON Schema or OpenAPI-generated types.

## Core Data Flow

### 1. Upload

Frontend sends a multipart request:

- file
- file name
- optional source label

Backend validates:

- extension is `csv` or `xlsx`
- size limits
- content type where possible
- upload belongs to an expected user/session model later

Backend stores:

- raw upload in `backend/storage/raw_uploads/`
- initial metadata record with dataset ID and upload status

### 2. Parse

Backend parsing service:

- loads the raw file
- reads sheet selection for `xlsx` if needed
- converts to canonical tabular structure
- infers column names and basic types
- captures summary metadata
- writes structured output to `backend/storage/parsed_datasets/`

Recommended canonical stored format:

- parsed tabular data in `parquet` or normalized `json`
- metadata in `json`

Even if the upload is Excel, an internal `parquet` representation is usually better for downstream analysis.

### 3. Analyze

User asks a question only after a dataset is available.

Backend prepares:

- dataset metadata summary
- allowed operation set
- safe prompt for the LLM

LLM returns a plan, for example:

- filter rows
- aggregate by column
- compute summary stats
- generate a derived table

### 4. Execute Safely

Backend sends an execution request to the sandbox runner with:

- dataset reference or mounted snapshot
- approved operation spec
- resource limits
- job ID

Sandbox runs against the isolated dataset copy and returns:

- result data
- logs
- execution status
- optional generated files

### 5. Return Results

Backend stores execution artifacts and returns a user-facing response for:

- tabular result preview
- summary explanation
- downloadable artifact links later

## Security Boundaries

This app should be built around explicit trust boundaries from day one.

### Main backend trust boundary

The backend is trusted to:

- validate uploads
- parse files
- store metadata
- define what operations are allowed

The backend is not trusted to safely execute arbitrary LLM-generated code in-process.

### Sandbox trust boundary

The Docker sandbox is where risky execution happens.

Minimum controls to implement:

- no host Docker socket inside the container
- no unrestricted outbound network
- per-job container lifecycle
- low privilege user inside container
- strict timeout
- memory/CPU caps
- read-only input mounts where possible
- separate output mount
- job-level audit logs

### LLM safety boundary

The LLM should produce structured intents, not free-form shell access.

Prefer this pattern:

1. LLM produces a structured action plan.
2. Backend validates the plan against an allowlist.
3. Only validated plans are converted into sandbox execution jobs.

Avoid:

- letting the model emit arbitrary shell commands directly
- letting the model choose arbitrary file paths
- giving the model raw infrastructure credentials

## Suggested Backend Domain Model

These entities will likely be enough to start:

### Dataset

- `id`
- `source_filename`
- `source_type` (`csv` or `xlsx`)
- `upload_status`
- `parse_status`
- `storage_path_raw`
- `storage_path_parsed`
- `row_count`
- `column_count`
- `schema_summary`
- `created_at`

### Analysis Job

- `id`
- `dataset_id`
- `user_prompt`
- `llm_plan`
- `status`
- `submitted_at`
- `completed_at`

### Execution Result

- `job_id`
- `result_type`
- `result_preview`
- `artifact_paths`
- `logs`
- `error_message`

## API Design Suggestions

Start with a small API surface:

### Dataset endpoints

- `POST /api/v1/datasets/upload`
- `GET /api/v1/datasets`
- `GET /api/v1/datasets/{dataset_id}`
- `GET /api/v1/datasets/{dataset_id}/preview`

### Analysis endpoints

- `POST /api/v1/analysis/jobs`
- `GET /api/v1/analysis/jobs/{job_id}`
- `GET /api/v1/analysis/jobs/{job_id}/result`

### Health endpoints

- `GET /api/v1/health`
- `GET /api/v1/sandbox/health`

## Development Plan

Build this in phases.

### Phase 1: Ingestion foundation

Implement:

- frontend upload screen
- backend upload endpoint
- file type validation
- raw file persistence
- parsing for `csv` and `xlsx`
- structured dataset metadata storage
- dataset preview endpoint

Definition of done:

- user uploads a file
- backend parses it successfully
- frontend can show dataset columns and sample rows

### Phase 2: LLM planning layer

Implement:

- dataset-aware analysis prompt construction
- structured output from the LLM
- operation allowlist validation
- job records and status tracking

Definition of done:

- user can ask an analysis question
- backend returns a validated execution plan

### Phase 3: Sandbox execution

Implement:

- sandbox Docker image
- isolated job runner
- dataset snapshot mounting
- resource limits
- execution result persistence

Definition of done:

- backend can submit a job to the sandbox
- sandbox returns structured results safely

### Phase 4: Production hardening

Implement:

- authentication and authorization
- object storage
- database persistence
- observability
- rate limiting
- audit trails
- retries and dead-letter handling

## Local Development Recommendations

Use separate services even in development:

- `frontend` on one port
- `backend` on one port
- optional local database later
- sandbox runner invoked as a separate Docker workload

Recommended local workflow:

1. Start the backend.
2. Start the frontend.
3. Upload a `csv` or `xlsx`.
4. Confirm parsing and preview work.
5. Add LLM planning.
6. Add sandbox execution.

## Implementation Notes

### Parsing strategy

For `csv`:

- detect delimiter safely
- normalize headers
- infer types conservatively

For `xlsx`:

- default to first sheet initially
- preserve sheet metadata
- reject unsupported workbook complexity for the first version

### Structured output format

Define a canonical parsed dataset object early. For example:

```json
{
  "dataset_id": "ds_123",
  "columns": [
    { "name": "order_id", "dtype": "string" },
    { "name": "amount", "dtype": "float" },
    { "name": "region", "dtype": "string" }
  ],
  "row_count": 1000,
  "preview_rows": [
    { "order_id": "A1", "amount": 10.5, "region": "APAC" }
  ]
}
```

### Execution contract

Do not pass raw prompts straight into the sandbox.

Prefer a validated execution payload such as:

```json
{
  "job_id": "job_123",
  "dataset_id": "ds_123",
  "operation": "aggregate",
  "params": {
    "group_by": ["region"],
    "metrics": [
      { "column": "amount", "agg": "sum", "as": "total_amount" }
    ]
  }
}
```

## Suggested Next Files To Add

After this scaffold, the next useful files would be:

- `frontend/package.json`
- `frontend/src/app/page.tsx` or equivalent
- `backend/pyproject.toml`
- `backend/app/main.py`
- `backend/app/api/v1/routes/datasets.py`
- `backend/app/services/parsing/csv_parser.py`
- `backend/app/services/parsing/xlsx_parser.py`
- `docker/sandbox/Dockerfile`
- `docker-compose.yml`

## Open Decisions

These are the main implementation choices you still need to lock in:

- frontend framework: Next.js vs React + Vite
- backend stack: Python vs Node.js
- database: Postgres vs SQLite for local-first development
- parsed data format: JSON vs Parquet
- queue model: synchronous first vs background jobs
- object storage: local disk first vs S3-compatible storage

## Recommended Defaults

If you want the most pragmatic first version, use:

- Next.js + TypeScript for frontend
- FastAPI + Python for backend
- pandas or polars for ingestion
- Parquet for parsed storage
- SQLite for local metadata at first
- Docker per analysis job for isolated execution

## Current State

This repository now contains the folder structure needed to start implementation. No runtime code has been added yet; only scaffolding and documentation have been created.
