# Oilora Blue AI — API Contract Registry

Status of the backend HTTP contract as of **Phase 2 (interactive map)**. This document is the
source of truth for what exists today; the TypeScript client in `frontend/src/lib/api.ts` mirrors
only the endpoints listed under *Implemented*.

## 1. Conventions

| Convention | Rule |
| --- | --- |
| Base path | `/api` |
| Identifiers | `case-<12 hex>`, `file-<12 hex>` (future domains follow `<domain>-<12 hex>`) |
| Timestamps | ISO 8601 UTC; case times are timezone-aware and stored normalized to canonical `YYYY-MM-DDTHH:MM:SS.mmmZ` |
| Request ID | Every response carries `X-Request-ID` (client-supplied value is propagated; otherwise a server-generated hex ID). |
| Security headers | `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `Permissions-Policy` (camera/geolocation/mic/etc. disabled). |
| CORS | Restricted to configured local frontend origins (`CORS_ORIGINS`). No wildcard with credentials. |

## 2. Standard error envelope

Two envelopes are used, both always carrying `X-Request-ID`:

- **Client errors** (400/404/413/422): FastAPI HTTPException envelope
  `{"detail": ...}` where `detail` is a safe, human-readable string, an object
  (`{message, errors, warnings}`, `{message, error_code, request_id}`), or — for
  case semantic validation — an array of `{loc, msg}` entries that the frontend
  renders as field-level errors.
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
| POST | `/api/cases` | `CaseCreate` | `BaseResponse{data:CaseDetail}` | 201; creates case. 422 with field-level `detail` array for invalid timestamps (naive/off-format), chronology (incident after observation), unreasonably-future dates, and degenerate/incomplete bounding boxes |
| GET | `/api/cases?offset&limit` | query | `PaginatedResponse{data:[CaseSummary]}` | totals from SQLite |
| GET | `/api/cases/{id}` | — | `BaseResponse{data:CaseDetail}` | includes `files` |
| PATCH | `/api/cases/{id}` | `CaseUpdate` | `BaseResponse{data:CaseDetail}` | metadata only; merged-case validation (same 422 rules as create) |
| DELETE | `/api/cases/{id}` | — | `BaseResponse` | cascades files/jobs/audit/viewport/manifests + case runtime dirs |
| GET | `/api/cases/{id}/status` | — | `BaseResponse{data:{status,current_stage,...}}` | processing position |
| POST | `/api/cases/{id}/files` | multipart `file` + `file_type` + optional SAR provenance (`product_identifier`, `acquisition_time` (tz-aware ISO), `provenance_source`, `polarization`) | `BaseResponse{data:FileInfo}` | 201; validated + SHA-256. SAR provenance stored in `metadata`; a derived GeoTIFF without provenance is never reported as verified Sentinel-1 |
| GET | `/api/cases/{id}/files` | — | `BaseResponse{data:[FileInfo]}` | registered files |
| GET | `/api/cases/{id}/files/{fid}` | — | `BaseResponse{data:FileInfo}` | single file |
| GET | `/api/cases/{id}/files/{fid}/manifest` | — | `BaseResponse{data:FileManifest}` | provenance manifest for a registered file (Gate 1): manifest id, source mapping, provider, product identifier, acquisition window, original + stored filename, byte size, SHA-256, media format, CRS/bounds/bands when readable, granular `validation_status`, validation messages, software version. Never contains filesystem paths |
| GET | `/api/sources` | — | `BaseResponse{data:[SourceInfo]}` | official provider registry (Gate 1): six seeded sources with honest `configured_status` — `connected` only after a successful real probe; `authentication_required` when credentials are absent; `not_verified` before any probe; `local_file_workflow` for file-based sources. Credential values never appear — only masked `authentication_configured: bool` |
| GET | `/api/sources/{id}` | — | `BaseResponse{data:SourceInfo}` | single registry source |
| POST | `/api/sources/{id}/test` | — | `BaseResponse{data:SourceInfo}` | real, time-limited connectivity probe (8 s timeout, 5 s cooldown). Credential-gated sources without credentials report `authentication_required` without network activity; local-file sources report `local_file_workflow`; results persist (`last_successful_access`, `last_failed_access`, error category) |
| GET | `/api/cases/{id}/map/summary` | — | `BaseResponse{data:MapSummary}` | genuine map readiness: bounds, time range, per-layer availability, integrity |
| GET | `/api/cases/{id}/map/layers` | — | `BaseResponse{data:{layers:[MapLayerInfo]}}` | typed layer registry with honest states + reasons |
| GET | `/api/cases/{id}/map/features` | `?layer=a,b` (default: all vector) | `BaseResponse{data:{layers:{id:FeatureState}}}` | GeoJSON for genuine layers; typed non-ready states otherwise |
| GET | `/api/cases/{id}/map/provenance` | — | `BaseResponse{data:Provenance}` | sources + derived artifacts, no filesystem paths |
| GET | `/api/cases/{id}/map/viewport` | — | `BaseResponse{data:ViewportResponse}` | saved + data-derived default viewport |
| PATCH | `/api/cases/{id}/map/viewport` | `ViewportState` | `BaseResponse{data:{viewport}}` | persists safe analyst viewport preference |
| GET | `/api/cases/{id}/map/sar-overlay` | — | `BaseResponse{data:SarOverlay}` | derived SAR preview descriptor (bounds/url/checksums) with granular `validation_status`: `uploaded`/`format_checked`/`geospatial_validated`/`sentinel1_verified`/`preview_ready`/`processing_blocked`/`invalid`; arbitrary TIFFs can never be `preview_ready` without a readable georeferenced raster and a derived preview matching the input checksum |
| GET | `/api/cases/{id}/map/sar-preview/{fid}` | — | `image/png` (200) or typed 404 | derived grayscale preview of the real registered raster |

OpenAPI: `/api/openapi.json`, docs UI at `/api/docs`.

**File response model (safe fields only):** every `FileInfo` response (upload, list, get,
case detail `files`) is sanitized. The absolute OS path (`file_path`) is **never** returned.
Safe fields: `id`, `case_id`, `file_type`, `original_filename`, `stored_filename`,
`file_size`, `mime_type`, `sha256_checksum`, `validation_status`, `validation_errors`,
`metadata`, `created_at`, `manifest_id`, and `download_available` (always `false` until an
authenticated, case-isolated download endpoint exists). SAR files additionally expose
their provenance in `metadata` (`product_identifier`, `acquisition_time`,
`provenance_source`, `polarization`) and their granular state via the map layer
registry / `sar-overlay` endpoint.

**Manifest validation vocabulary (per-file, distinct from the map layer state):**
`uploaded` / `format_checked` / `geospatial_validated` / `source_verified` /
`processing_ready` / `derived` / `rejected` / `processing_blocked`. SAR manifests are
derived from the real runtime: rasterio unavailable → `processing_blocked`;
unreadable/non-georeferenced raster → `rejected`; readable raster →
`geospatial_validated`; readable + declared Sentinel-1 provenance → `source_verified`
(declared only — content-level product verification is a later gate).

**Case validation rules (create + patch):**

- Timestamps must be timezone-aware ISO 8601; naive values are rejected (422).
- Stored timestamps are normalized to UTC; `incident_time` must not be after `observation_time`.
- Dates more than 24 h in the future are rejected (no scheduling workflow is documented).
- Bounding boxes must be all-or-none, finite, within WGS 84 (`lat ∈ [-90, 90]`, `lon ∈ [-180, 180]`),
  with `min < max` on both axes (zero-area boxes rejected).
- Errors are returned as a 422 `detail` array of `{loc, msg}` entries for field-level display.

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

## 6. Map layer state semantics (Phase 2)

`map/layers` returns one entry per registry layer (the server-side registry in
`backend/app/services/map_service.py` is the single source of truth for layer ids and
z-order; the client never fabricates a layer state). Typed states:

| State | Meaning | Example reason shown to analyst |
| --- | --- | --- |
| `ready` | genuine data exists and can render | — |
| `not_processed` | the scientific stage that produces the layer has not run | "Detection has not been executed." |
| `missing_input` | the stage's required registered input is absent | "SAR imagery (Sentinel-1 GeoTIFF) has not been registered." |
| `failed` | input corrupt / stage failed | "Registered boundary file is not valid GeoJSON." |
| `coverage_mismatch` | sources exist but do not overlap | reserved for Phase 3+ adapters |
| `empty` | a valid stage completed with no output | reserved for Phase 3+ results |
| `unavailable` | support/config absent (library, dataset, source) | "Coastline dataset not configured." |
| `processing` / `awaiting_review` | job in flight / output awaiting analyst | — |

Feature responses distinguish "available but empty" from "not processed": a layer that
never ran returns `features: null` plus a typed non-ready `state` and a `reason` - never a
misleading empty FeatureCollection.

Real data rendered today: investigation-area polygon (case bbox in SQLite), registered
GeoJSON boundary files (validated in the backend), and a derived grayscale SAR preview
(rasterio, cached by input SHA-256 and recorded in `map/provenance` as a derived artifact).