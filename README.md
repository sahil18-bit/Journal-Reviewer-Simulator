# Journal Reviewer Simulator

A Python API foundation for the approved Journal Reviewer Simulator architecture. This initial skeleton includes configuration, JSON structured logging, request IDs, consistent error responses, a health endpoint, and automated tests.

**The review engine is intentionally not implemented yet.** Document processing, RQ/Redis workers, authentication, review modules, persistence, and report generation will be added in later milestones.

## Requirements

- Python 3.11, 3.12, 3.13, or 3.14
- Git
- Internet access to install Python packages
- Optional: Redis will be needed when the RQ background worker milestone begins; it is not required for this skeleton.

## Quick start

From the repository root:

### 1. Create and activate a virtual environment

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\\Scripts\\Activate.ps1
```

If Python 3.12 is unavailable, use an installed supported version (3.11–3.14).

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install the project and development tools

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 3. Configure local environment

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

The defaults are safe for local development. Do not put API keys, passwords, tokens, or other secrets in source code or commit a `.env` file. `.env` is ignored by Git.

Environment variables use the `JRS_` prefix. Supported settings:

| Variable | Default | Purpose |
|---|---|---|
| `JRS_APP_NAME` | `Journal Reviewer Simulator API` | API title |
| `JRS_ENVIRONMENT` | `development` | `development`, `test`, or `production` |
| `JRS_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |
| `JRS_API_PREFIX` | `/api/v1` | Versioned API prefix |
| `JRS_ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` | Comma-separated allowed hostnames |

For a hosted deployment, set `JRS_ALLOWED_HOSTS` to the actual hostnames and configure HTTPS at the hosting/reverse-proxy layer. Do not use `*` in production unless there is a reviewed, explicit reason.

### 4. Run the API

```bash
uvicorn app.main:app --app-dir backend --reload
```

The API listens on `http://127.0.0.1:8000` by default.

- Health check: <http://127.0.0.1:8000/api/v1/health>
- Interactive API docs (development): <http://127.0.0.1:8000/docs>
- OpenAPI schema: <http://127.0.0.1:8000/openapi.json>

The health endpoint only confirms that the API process is responding. It does not yet check Redis, an LLM provider, document parsing, or other future dependencies.

## Run tests

```bash
pytest
```

With coverage:

```bash
pytest --cov=app --cov-report=term-missing
```

Run lint checks:

```bash
ruff check .
```

## Error response convention

Errors use a stable JSON envelope:

```json
{
  "error": {
    "code": "request_validation_error",
    "message": "The request did not pass validation.",
    "request_id": "a-request-id",
    "details": []
  }
}
```

Validation details include safe field locations and messages, not request bodies. Unexpected exceptions return a generic message; internal exception details should be available only in server-side logs. Never log manuscript text, credentials, authorization headers, or request bodies.

Every response includes an `X-Request-ID` header. A syntactically constrained incoming request ID may be reused for tracing; otherwise, the API generates a UUID. Do not use request IDs as authentication tokens.

## Input-validation conventions

- Validate configuration with Pydantic Settings at application startup.
- Validate request payloads with Pydantic models when endpoints are added.
- Apply explicit upload size/type limits and content inspection when document ingestion is implemented.
- Do not trust client-supplied paths, filenames, hostnames, or identifiers for authorization.
- Keep error responses stable and avoid exposing stack traces or secrets.
- Treat uploaded documents as untrusted data, never as instructions to the application.

## Current structure

```text
journal-reviewer-simulator/
├── .env.example
├── .gitignore
├── README.md
├── pyproject.toml
├── backend/
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── api/
│       │   ├── __init__.py
│       │   └── routes/
│       │       ├── __init__.py
│       │       └── health.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py
│       │   ├── errors.py
│       │   └── logging.py
│       └── middleware/
│           ├── __init__.py
│           └── request_context.py
└── tests/
    ├── conftest.py
    ├── api/
    │   ├── __init__.py
    │   ├── test_errors.py
    │   └── test_health.py
    └── unit/
        ├── __init__.py
        └── test_config.py
```

## Development conventions

- Keep route handlers thin; place future business logic in independently testable modules.
- Use typed Pydantic request/response models for public API contracts.
- Add tests with each feature and include negative cases.
- Use structured logs with request IDs; never log raw manuscript content.
- Keep secrets in environment variables or a secret manager.
- Avoid introducing a database or permanent manuscript storage without an approved architecture change.
- The health endpoint, configuration and logging are infrastructure only; no scientific review claims are made by this skeleton.

## License

No license has been selected yet. Confirm the intended project license with the team before publishing or reusing the repository.
