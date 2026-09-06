# OILORA BLUE AI

**Maritime oil-spill intelligence platform — SIH26143**

Oilora Blue AI is a local-first, evidence-based maritime oil-spill investigation and
decision-support web application. It is being built to detect possible marine oil slicks
from **real Sentinel-1 SAR imagery**, reconstruct backward and forward drift from **real
environmental forcing data**, correlate **real AIS vessel trajectories**, and produce
**explainable, reproducible evidence**.

It is a decision-support system. It never declares a vessel guilty — it produces candidate
vessels, evidence compatibility, confidence levels, and investigation priorities that
require human verification.

---

## 1. The problem in plain English

When a possible oil slick is spotted in satellite radar imagery, an analyst needs to answer:
where might the oil have come from, when might it have been released, and which vessels were
in a position to be associated with it? Answering this requires combining SAR imagery,
wind and ocean-current data, vessel tracking (AIS) records, and a transparent scoring
framework — all while preserving the provenance and integrity of every input and output so
the analysis can be audited later.

## 2. Current verified capabilities (Phase 1)

| Capability | Status |
| --- | --- |
| Next.js + React + TypeScript + Tailwind frontend | ✅ Working |
| FastAPI + Pydantic + SQLite backend | ✅ Working |
| Case management (create, list, update, delete, status) | ✅ Working |
| Secure file registration (SAR / AIS / environmental / mask) | ✅ Working |
| Streamed SHA-256 checksums, magic-byte + size + extension + path validation | ✅ Working |
| Request-ID header on every response + security headers | ✅ Working |
| Temporary-upload cleanup on success and failure | ✅ Working |
| Sanitized 500 errors (no internal details leaked) | ✅ Working |
| Oilora Blue AI branding + ocean design system (no purple) | ✅ Working |
| Local Demo Mode (no fake authentication) | ✅ Working |
| Backend tests (56 passing), frontend typecheck, production build | ✅ Working |
| Git version control, ruff lint baseline, split dependency files | ✅ Working |

## 3. Honest list of capabilities **not yet implemented**

The following are **not** implemented and are **never** simulated with dummy data:

- ❌ SAR preprocessing and raster validation (Phase 2)
- ❌ ONNX oil-slick detection inference (Phase 2)
- ❌ Detection review interface and georeferenced map layers (Phases 2–3)
- ❌ Environmental (wind/current) NetCDF validation (Phase 3)
- ❌ Backward / forward drift simulation (Phase 3)
- ❌ AIS ingestion, quality reports, trajectory reconstruction (Phase 3)
- ❌ Candidate filtering and explainable scoring (Phase 4)
- ❌ Evidence manifests and investigation reports (Phase 4)
- ❌ Authentication and role-based access (Phase 5)
- ❌ Offline prepared real-data demonstration package (Phase 5)

Until those phases land, the interface shows honest states such as
`Not available`, `Pending`, and `No investigations yet` — it never fabricates scientific
results.

## 4. Approved architecture

```
frontend/   Next.js 15, React 19, TypeScript, Tailwind CSS (MapLibre GL JS from Phase 3)
backend/    Python, FastAPI, Pydantic, SQLite (built-in sqlite3 module)
models/     ONNX model artifacts (empty until Phase 2)
data/       Case-isolated local storage (uploads, outputs, case artifacts)
docs/       Design documents and contract registry
scripts/    PowerShell setup / start / verify / stop scripts
```

- The frontend renders and interacts; it **never calculates scientific results**.
- All scientific outputs will originate from FastAPI services.
- SQLite stores structured case data; large files live in case-isolated directories with
  relative paths stored in the database.
- No cloud database, paid API, blockchain, or chatbot is used or planned.

## 5. Target hardware

- AMD Ryzen 7 CPU, AMD Radeon integrated graphics, 16 GB RAM, 1 TB storage
- Windows laptop; desktop, tablet, and mobile browsers
- Local-first and offline-capable (prepared demonstration requires no internet at runtime)

## 6. Zero-cost policy

Only free and open-source software, free public datasets (Copernicus Data Space Ecosystem,
NOAA MarineCadastre, public NetCDF providers, Natural Earth), and free CI capabilities are
used. No paid API, paid map service, or paid infrastructure is introduced. Any integration
that requires an account documents exactly which account, where the key is obtained, and
which environment variable holds it — credentials are never placed in frontend code.

## 7. Real-data policy (non-negotiable)

- The application contains **no fabricated scientific information**.
- Every dataset must have a provenance record (publisher, URL/DOI, licence, download date,
  acquisition time, bounds, CRS, format, checksum, transformations).
- Datasets are correlated only when their geographic and temporal coverage genuinely
  overlap; otherwise correlation is blocked and the incompatibility is explained.
- If real data is missing, the interface shows honest states — never silent dummy output.
- Cached/prepared results are allowed only when produced by the actual pipeline with
  matching input checksums, model checksum, and configuration, and are labelled as
  previously computed verified results.

## 8. Prerequisites

- Python **3.10+** (tested on 3.14) — with `venv` support
- Node.js **18+** and npm
- Windows PowerShell 5.1+ (the scripts use `Start-Process`, `taskkill`, `Get-NetTCPConnection`)

## 9. Setup (Windows PowerShell)

From the repository root:

```powershell
.\scripts\setup.ps1
```

This checks prerequisites, creates `backend\.venv`, installs backend core + dev
dependencies, and runs `npm ci` in `frontend/`. It does not modify anything outside the
repository and never deletes user files.

Optional environment configuration: copy `backend\.env.example` to `backend\.env` and
adjust as needed. All settings have safe defaults; a `.env` is not required to run.

## 10. Run (Windows PowerShell)

```powershell
.\scripts\start.ps1        # starts backend (port 8000) and frontend (port 3000)
.\scripts\verify.ps1       # checks health, DB, and both servers
.\scripts\stop.ps1         # stops only processes started for Oilora Blue AI
```

Or run manually:

```powershell
# Terminal 1 — backend
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev -- -p 3000
```

- Frontend: **http://localhost:3000** — API requests under `/api/*` are proxied to the
  backend on port 8000 (`frontend/next.config.js`).
- Backend: **http://127.0.0.1:8000** — API docs at `/api/docs`.

## 11. Health and status endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Backend process is alive; returns version. |
| `GET /api/system/status` | Genuine checks: database connectivity, model availability, disk space, offline readiness, Local Demo Mode. |

## 12. Tests, lint, typecheck, build

```powershell
# Backend (inside backend/)
.\.venv\Scripts\python.exe -m pytest -q        # 56 tests
.\.venv\Scripts\ruff.exe check .               # lint
.\.venv\Scripts\ruff.exe format --check .      # formatting

# Frontend (inside frontend/)
npm run typecheck                              # tsc --noEmit
npm run test:run                               # Vitest unit tests
npm run lint                                   # ESLint
npm run build                                  # production build
```

## 13. Local Demo Mode

With `ENABLE_LOCAL_DEMO_MODE=true` (the default) the application runs in **Local Demo
Mode**: a single-user local workflow with no accounts. It is clearly labelled in the
interface. It is not a fake login — there is no authentication screen at all. Role-based
access (Administrator / Analyst / Reviewer / Viewer) is planned for a later phase.

## 14. Dataset provenance requirement

Before any scientific processing, every registered file must carry a provenance record.
The `files` table stores metadata, and future phases will require the full provenance
fields (dataset title, publisher, official URL/DOI, licence, download date, acquisition
time, geographic bounds, CRS, format, original filename, size, SHA-256 checksum, and
transformations). Do not upload datasets without their provenance.

## 15. Security notes

- **Never commit `.env`.** It is git-ignored; `.env.example` contains names only.
- CORS is restricted to configured local frontend origins — no wildcard with credentials.
- Uploads are validated by extension, magic bytes, size, filename, and path safety, stored
  in case-isolated directories, and checksummed with SHA-256.
- Every HTTP response carries an `X-Request-ID`; unexpected errors return a sanitized
  response with that ID and log the full detail server-side only.
- The database path is configured once via `DATABASE_PATH` and resolved to an absolute
  path internally; clients can never supply a database path.

## 16. Current limitations (Phase 1)

- No scientific processing yet: no SAR validation, detection, drift, AIS analysis, or
  candidate scoring.
- No MapLibre map yet (Phase 3).
- The 2 GB upload limit is a logical limit; dataset-specific and deployment-specific lower
  limits will be added in later phases.
- Background job execution, rate limiting, authentication, and report generation are not
  implemented.
- Detached dev servers do not survive a machine or FreeBuff restart — run
  `scripts\start.ps1` again to bring them back.

## 17. Folder structure

```
oilora-blue-ai/
├── backend/
│   ├── app/            FastAPI application (config, database, models, routers, services)
│   ├── tests/          Pytest suite (56 tests)
│   ├── requirements*.txt   Core / geo / science / dev / training dependency split
│   ├── ruff.toml       Lint configuration
│   └── .env.example    Environment template (names only)
├── frontend/
│   ├── src/app/        Next.js pages (dashboard, new, status, case detail)
│   ├── src/components/ App shell, header, sidebar
│   ├── src/lib/api.ts  Typed API client + shared types
│   └── tests/          Vitest unit tests
├── data/               Local storage (uploads, cases, outputs — git-ignored)
├── models/             ONNX artifacts (empty until Phase 2)
├── docs/               Design docs and API contract registry
├── scripts/            PowerShell setup / start / verify / stop
└── .github/workflows/  CI pipeline
```

## 18. Phase plan

- **Phase 1 (this phase):** reproducible baseline — Git, config truth, security hardening,
  dependency split, docs, scripts, CI, frontend quality baseline.
- **Phase 2:** real SAR validation and preprocessing, ONNX detection, detection review.
- **Phase 3:** MapLibre intelligence map, environmental validation, drift, AIS.
- **Phase 4:** candidate filtering and scoring, evidence manifests, investigation reports.
- **Phase 5:** authentication, rate limiting, caching, offline prepared-case package,
  regression and performance testing.