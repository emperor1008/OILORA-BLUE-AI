# Oilora Blue AI — API Contract Registry

Status of the backend HTTP contract as of **Phase 1**. This document is the source of
truth for what exists today; the TypeScript client in `frontend/src/lib/api.ts` mirrors
only the endpoints listed under *Implemented*.

## 1. Conventions

| Convention | Rule |
| --- | --- |
| Base path | `/api` |
| Identifiers | `case-<12 hex>`, `file-<12 hex>` (future domains follow `<domain>-<12 hex>`) |
| Timestamps | ISO 8601 UTC, e.g. `2024-01-15T10:30:00+00:00` |
| Request ID | Every response carries `X-Request-ID` (client-supplied value is propagated; otherwise a server-generated hex ID). |
| Security headers | `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `Permissions-Policy` (camera/geolocation/mic/etc. disabled). |
| CORS | Restricted to configured local frontend origins (`CORS_ORIGINS`). No wildcard with credentials. |

## 2. Standard error envelope

Two envelopes are used, both always carrying `X-Request-ID`:

- **Client errors** (400/404/413/422): FastAPI HTTPException envelope
  `{"detail": ...}` where `detail` is a safe, human-readable string or an object
  (`{message, errors, warnings}`, `{message, error_code, request_id}`).
- **Unexpected server errors** (500): `{"success": false, "message": "Internal server
  error" | "Upload failed", "error_code": "INTERNAL_ERROR" | "UPLOAD_FAILED",
  "request_id": "<id>"}`. Internal exception details are logged server-side only and
  never returned to the client.

## 3. Implemented endpoints (live)

| Method | Path | Request | Response | Notes |
| --- | --- | --- | --- | --- |
| GET | `/` | — | app info JSON | name, version, docs, health links |
| GET | `/api/health` | — | `BaseResponse{data:{version}}` | liveness |
| GET | `/api/system/status` | — | `BaseResponse{data:SystemStatus}` | genuine DB/model/disk/offline checks |
| POST | `/api/cases` | `CaseCreate` | `BaseResponse{data:CaseDetail}` | 201; creates case |
| GET | `/api/cases?offset&limit` | query | `PaginatedResponse{data:[CaseSummary]}` | totals from SQLite |
| GET | `/api/cases/{id}` | — | `BaseResponse{data:CaseDetail}` | includes `files` |
| PATCH | `/api/cases/{id}` | `CaseUpdate` | `BaseResponse{data:CaseDetail}` | metadata only |
| DELETE | `/api/cases/{id}` | — | `BaseResponse` | cascades files/jobs |
| GET | `/api/cases/{id}/status` | — | `BaseResponse{data:{status,current_stage,...}}` | processing position |
| POST | `/api/cases/{id}/files` | multipart `file` + `file_type` | `BaseResponse{data:FileInfo}` | 201; validated + SHA-256 |
| GET | `/api/cases/{id}/files` | — | `BaseResponse{data:[FileInfo]}` | registered files |
| GET | `/api/cases/{id}/files/{fid}` | — | `BaseResponse{data:FileInfo}` | single file |

OpenAPI: `/api/openapi.json`, docs UI at `/api/docs`.

## 4. Planned endpoints — NOT IMPLEMENTED

The following are part of the product roadmap but **do not exist yet**. No route returns
empty success objects for them; calling them yields 404.

| Area | Planned routes | Phase |
| --- | --- | --- |
| SAR preprocessing | `POST /api/cases/{id}/preprocess` | 2 |
| Detection | `POST /api/cases/{id}/detect`, `GET .../detections` | 2 |
| Detection review | `POST /api/cases/{id}/detections/{did}/review` | 2 |
| Environmental | `POST /api/cases/{id}/environmental` validation | 3 |
| Drift | `POST /api/cases/{id}/drift/backward`, `.../forward` | 3 |
| AIS | `POST /api/cases/{id}/ais/process`, `GET .../ais/quality`, `GET .../tracks` | 3 |
| Candidates | `GET /api/cases/{id}/candidates` | 4 |
| Evidence | `POST /api/cases/{id}/manifest`, `GET .../manifests` | 4 |
| Reports | `POST /api/cases/{id}/report`, `GET .../reports/{rid}` | 4 |
| Jobs | read-only job list/status once the first scientific service exists | 2+ |

The dormant Pydantic schemas under `backend/app/models/` (`detection.py`, `drift.py`,
`ais.py`, `candidates.py`, `evidence.py`, `jobs.py`) are **internal scaffolding only**.
A schema is not a working feature, and none of them are exposed as endpoints.

## 5. Job model & lifecycle safety (Phase-1 rules)

**Schema (already in SQLite, `jobs` table):** `id`, `case_id` (FK → cases, ON DELETE
CASCADE), `stage`, `status`, `progress`, `configuration`, `config_version`, `error_code`,
`error_message`, `retry_count`, `max_retries`, `started_at`, `completed_at`,
`created_at`.

**Allowed statuses (CHECK constraint):** `queued`, `validating`, `processing`,
`awaiting_review`, `completed`, `failed`, `cancelled`.

**Ownership:** every job belongs to exactly one case; deleting a case deletes its jobs.

**Phase-1 rules:**

- There is **no public job-update endpoint**. Clients can never set a job's status,
  progress, or error fields. Arbitrary client-driven `completed` transitions are
  impossible by design.
- No job executor exists yet; job execution and retry are implemented only together with
  the first real scientific SAR service (Phase 2).
- Future transition rules (to be enforced by backend services, never frontend payloads):
  - `queued → validating → processing → awaiting_review → completed`
  - any active state → `failed` (service-detected error) or `cancelled` (safe cancel).
  - Only the owning service may advance a job; transitions are logged to `audit_log`.