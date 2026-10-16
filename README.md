# Journal Reviewer Simulator

Upload a research paper (PDF) and get a simulated journal peer review: major and minor
concerns with evidence quotes and page numbers, a statistical and baseline critique, questions
to the authors, and an advisory recommendation (Accept / Minor Revision / Major Revision /
Reject), written in the **Deep Technical Critique** template.

The reviewer is a chain of prompts, each built from patterns taught in the Vanderbilt
"Prompt Engineering for ChatGPT" course:

| Step | What it does | Prompt patterns |
|---|---|---|
| 1. Paper analyst | Extracts claims, methods, data, metrics, tests, baselines | Persona, Template, Context Manager |
| 2. Three reviewers | Methodology, statistics and baseline reviews | Cognitive Verifier, Persona, Few-shot, Chain of Thought, Template |
| 3. Fact check | Rejects any finding whose quote is not in the PDF | Fact Check List |
| 4. Handling editor | Merges, classifies major/minor, decides, asks questions | Persona, Recipe, Reflection, Template, Tail Generation |

All prompts are in `backend/app/reviewer/prompts.py`. A worked example (a made-up paper with
deliberate flaws, the exact prompts sent, the replies and the final report) is in `samples/`:
run `python3 samples/run_sample.py` to replay it.

The project foundation (configuration, logging, request IDs, error handling, health endpoint)
comes from the first development phase and is unchanged.

## How to run (one click)

1. Open this folder in VS Code.
2. Open `run.py` (or `backend/app/main.py`) and click **Run**.
   - First run only: it installs what it needs (about a minute, needs internet) and asks once
     for an AI API key (Gemini, OpenAI or Claude; a free Gemini key:
     https://aistudio.google.com/apikey). Press Enter to skip.
3. The browser opens. Drop a research paper (PDF), click **Review paper**, read the review.
   **Download review** saves it in the Deep Technical Critique format.
4. Press Ctrl+C in the terminal to stop.

Without a key (or if the AI service cannot be reached) the built-in checklist reviews the paper,
so a review is always produced. To change the key, delete `.env` and run again, or use the small
"AI key" link at the bottom of the page.

Needs Python 3.9 or newer (`python3` on macOS). Terminal alternative: `python3 run.py`.

Optional settings can go in a `.env` file (copy `.env.example`); the key typed on the page is
used for that request only and is never stored on the server.

| Variable | Default | Purpose |
|---|---|---|
| `JRS_LLM_PROVIDER` | `none` | `gemini`, `openai` or `anthropic` (lets you skip the key box) |
| `JRS_LLM_API_KEY` | empty | API key for that provider |
| `JRS_LLM_MODEL` | provider default | e.g. `gemini-flash-latest`, `gpt-4o-mini` |
| `JRS_MAX_UPLOAD_MB` / `JRS_MAX_PAGES` | `15` / `40` | Upload limits |
| `JRS_LOG_LEVEL` | `INFO` | Logging level |

Endpoints: `POST /api/v1/reviews` (PDF, optional `api_key`), `GET /api/v1/reviews/config`,
`GET /api/v1/health`.

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

## Structure

```text
backend/app/
├── main.py                 # app + web page route
├── api/routes/health.py    # health check
├── api/routes/review.py    # review endpoints
├── core/                   # config, logging, error envelope
├── middleware/             # request IDs
├── reviewer/
│   ├── pdf_reader.py       # PDF -> page-numbered text
│   ├── prompts.py          # every prompt, labelled with its prompt pattern
│   ├── llm.py              # Gemini / OpenAI / Anthropic client
│   ├── pipeline.py         # the prompt chain, fact check, report template
│   └── checklist.py        # built-in checklist used when no AI key is available
└── static/index.html       # upload page and review dashboard
samples/                    # sample paper, saved prompts/replies, sample report
run.py                      # one-click start (installs, asks for the key once, opens the browser)
tests/                      # 35 automated tests (a fake LLM is used; no key needed)
```

## Development conventions

- Keep route handlers thin; place future business logic in independently testable modules.
- Use typed Pydantic request/response models for public API contracts.
- Add tests with each feature and include negative cases.
- Use structured logs with request IDs; never log raw manuscript content.
- Keep secrets in environment variables or a secret manager.
- Uploaded papers are processed in memory and never stored.
- The review is advisory: it supports, but does not replace, expert peer review.

## License

No license has been selected yet. Confirm the intended project license with the team before publishing or reusing the repository.
