# docker/

Short description

Houses container build contexts and helper scripts used for isolated execution and local development. The primary purpose is the sandbox image where user-approved analysis runs safely outside the main service process.

Primary responsibilities

- Provide a minimal, audited `Dockerfile` for the sandbox runner.
- Include a small runner/entrypoint script that executes the approved job spec and writes artifacts to a designated output directory.
- Define recommended resource limits, timeout behavior, and network restrictions.
- Provide `docker-compose.yml` or helper scripts for local development only.

Security & runtime rules

- Do not include secrets or host credentials in images.
- Run as a non-root user and minimize installed packages.
- Mount dataset snapshot read-only and expose only a writable artifacts directory.
- Deny or tightly restrict outbound network access for execution jobs.
- Ensure per-job container lifecycle and automated cleanup.

Notes

- The sandbox is an execution boundary; keep it separate from the main API image.
- Add CI steps to scan images for vulnerabilities before use in production.
