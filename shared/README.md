# shared/

Short description

Contains portable contracts and type definitions used by both frontend and backend to ensure consistent payload shapes and validation rules.

Primary responsibilities

- Store JSON Schema, OpenAPI components, or small canonical example payloads for dataset metadata, job requests, and result payloads.
- Provide generation scripts or guidance for creating TypeScript/Python types from the schemas.
- Keep common constants (`job_status`, `result_type`, header names like `X-Request-ID`) here.
- Include sample request/response examples for API consumers and tests.

Notes

- Treat these artifacts as the single source of truth for API contracts.
- Ensure backward-compatible evolution (versioning) and update generated types whenever schemas change.
