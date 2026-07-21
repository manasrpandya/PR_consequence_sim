# Local API

FastAPI serves interactive OpenAPI documentation at `http://localhost:8000/docs`.

- `GET /health`
- `GET /api/v1/repositories`
- `GET /api/v1/repositories/{repository_id}/pull-requests`
- `GET /api/v1/pull-requests/{pull_request_id}`
- `POST /api/v1/pull-requests/{pull_request_id}/analyze`
- `POST /api/v1/pull-requests/{pull_request_id}/simulate`
- `GET /api/v1/pull-requests/{pull_request_id}/ground-truth`
- `POST /api/v1/github/inspect` — JSON `{ "url": "https://github.com/.../pull/123" }`
- `POST /api/v1/github/analyze` — analyze an inspected public PR
- `POST /api/v1/uploads/inspect` — multipart `archive` (`.zip`) and `diff` (`.diff`/`.patch`)
- `POST /api/v1/uploads/analyze` — repeat the validated project and diff to run the pipeline
- `POST /api/v1/git-bundles/inspect` — multipart `bundle` (`.bundle`)
- `POST /api/v1/git-bundles/analyze` — multipart `bundle`, `base`, and `head`

Unknown IDs return a JSON 404. CORS permits only `http://localhost:3000` for local development.

Upload failures use a stable envelope: `{ "error": { "code": "...", "message": "..." } }`.
Codes include `unsupported_type`, `corrupt_archive`, `invalid_bundle`, `missing_diff`,
`path_mismatch`, `archive_limit_exceeded`, `extraction_failure`, `no_analyzable_source`,
`invalid_git_refs`, `timeout`, and `internal_analysis_failure`. Responses never expose temporary
paths or tracebacks. Inspection is deliberately separate from analysis; because local requests are
stateless and temporary data is cleaned immediately, the client resubmits the same evidence for the
explicit analysis step.
