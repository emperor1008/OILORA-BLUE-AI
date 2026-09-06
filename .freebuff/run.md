# Oilora Blue AI — Preview Run Doc

## Reproduce the uncommitted artifacts

1. Frontend dependencies (lockfile is committed):
   ```bash
   cd frontend && npm ci --no-audit --no-fund
   ```
   (or `npm install` when adding new devDependencies first)
2. Backend: create `backend/.venv` and install core + dev requirements once:
   ```bash
   cd backend && python -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements.txt -r requirements-dev.txt
   ```
   No `.env` file is required — `backend/app/config.py` provides defaults (port 8000, SQLite at `backend/oilora_blue.db`, data dir `data/`).

## Run the servers

Prefer the repository scripts (fixed ports, PID tracking, health checks):

```powershell
.\scripts\setup.ps1    # one time
.\scripts\start.ps1    # backend on 127.0.0.1:8000, frontend on localhost:3000
.\scripts\stop.ps1     # stop only Oilora Blue AI processes
```

Manual equivalent:

1. Backend (FastAPI, port 8000):
   ```bash
   cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
2. Frontend (Next.js dev server, fixed port 3000):
   ```bash
   cd frontend && npm run dev -- -p 3000
   ```
   The `next.config.js` rewrite proxies `/api/*` to `http://localhost:8000/api/*`.
3. Open the frontend URL; the Investigation Dashboard reads real case counts from `/api/cases`.