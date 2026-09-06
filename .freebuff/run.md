# Oilora Blue AI — Preview Run Doc

## Reproduce the uncommitted artifacts

1. Frontend dependencies (no lockfile is committed; install generates `frontend/package-lock.json`):
   ```bash
   cd frontend && npm install --no-audit --no-fund
   ```
2. Backend: uses globally installed Python packages (fastapi, uvicorn, pydantic, etc.). No `.env` file is required — `backend/app/config.py` provides defaults (port 8000, SQLite at `backend/oilora_blue.db`, data dir `data/`).

## Run the servers

1. Backend (FastAPI, port 8000):
   ```bash
   cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
2. Frontend (Next.js dev server):
   ```bash
   cd frontend && npm run dev
   ```
   Next.js auto-selects a free port when 3000 is busy (observed: 51150). The `next.config.js` rewrite proxies `/api/*` to `http://localhost:8000/api/*`.
3. Open the frontend URL; the Investigation Dashboard reads real case counts from `/api/cases`.