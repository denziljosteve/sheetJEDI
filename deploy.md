# sheetJEDI — Deployment Guide (verified commands)

Everything in the **“Verified”** sections below was executed in the build environment
(Windows 11, Python 3.12, Node 24) and produced the results recorded in
[PROGRESS.md](PROGRESS.md). Anything **unverified** is clearly marked — this project never
presents untested steps as working.

For the production hardening checklist (secrets, TLS, reverse proxy, backups), see
[PRODUCTIONDEPLOY.md](PRODUCTIONDEPLOY.md).

---

## 1. Prerequisites

| Requirement | Version used here | Notes |
|---|---|---|
| Python | **3.12** (`py -3.12`) | 3.14 exists on PATH but 3.12 chosen for ecosystem stability (decision D-001 context) |
| Node.js + npm | 24.15.0 / 12.0.2 | Frontend build & tests |
| Disk | ~500 MB | venv + node_modules + dist |
| Network | outbound HTTPS | Only when calling an AI provider (or installing deps) |

Docker is **not** installed in the build environment; Docker-based steps below are marked
unverified.

## 2. Environment configuration

```powershell
Copy-Item .env.example backend\.env     # then edit values
```

Key settings (full list in `.env.example`):

| Variable | Purpose | Default |
|---|---|---|
| `SHEETJEDI_ENV` | `development` / `production` | `development` |
| `SHEETJEDI_SECRET_KEY` | Fernet master key for provider-key encryption | dev: auto-generated keyfile · **prod: REQUIRED** |
| `SHEETJEDI_DATABASE_URL` | SQLite file or PostgreSQL DSN | `sqlite:///./data/sheetjedi.db` |
| `SHEETJEDI_CORS_ORIGINS` | Allowed origins (dev server) | `http://localhost:5173,…` |
| `SHEETJEDI_RATE_LIMIT_*` | In-memory sliding window | 30 req/min |
| `SHEETJEDI_MAX_UPLOAD_MB` | Upload cap | 10 |

Provider API keys are **never** set via environment variables — they are entered in
**Settings → AI Providers**, stored encrypted in the database, and only masked hints are ever
returned.

## 3. Verified: first-time setup

```powershell
# Backend
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m alembic upgrade head        # creates data\sheetjedi.db (4 tables)

# Frontend
cd ..\frontend
npm install
```

**Verified result:** `alembic upgrade head` on a fresh DB creates `app_settings`, `files`,
`provider_configs`, `solutions`.

## 4. Verified: development mode (two processes)

```powershell
# Terminal 1 — API
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — UI with hot reload (proxies /api → :8000)
cd frontend
npm run dev                                  # http://localhost:5173
```

**Verified result:** `GET http://127.0.0.1:8000/api/v1/health` →
`{"status":"ok","version":"0.1.0"}`; UI loads at `http://localhost:5173` with live data
(provider strip shows real database state).

> Note: `npm run dev` binds **IPv6 localhost** on this machine — use `http://localhost:5173`
> (not `127.0.0.1`) in the browser.

## 5. Verified: single-process production build

FastAPI serves the built SPA (`frontend/dist`) with history fallback, so one process answers
UI + API on one port.

```powershell
# 1. Build the UI
cd frontend
npm run build                                # tsc -b && vite build → dist/

# 2. Run the API + UI together
cd ..\backend
$env:SHEETJEDI_ENV = "production"
$env:SHEETJEDI_SECRET_KEY = "<your Fernet key>"     # required in production
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Verified result:**
- `GET http://127.0.0.1:8000/` → the sheetJEDI SPA (200, correct title)
- `GET http://127.0.0.1:8000/generate/formula` → SPA fallback (200)
- `GET http://127.0.0.1:8000/assets/*` → built JS/CSS
- `GET http://127.0.0.1:8000/api/v1/does-not-exist` → structured JSON 404 (never HTML)
- Covered by `backend/tests/test_spa_serving.py` (includes path-traversal guard)

Generate a production key once:

```powershell
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 6. Verified: upgrades & data migration

```powershell
cd backend
# 1. backup the SQLite file (it's just a file)
Copy-Item data\sheetjedi.db data\sheetjedi.backup-$(Get-Date -Format yyyyMMdd-HHmmss).db
# 2. apply migrations
.\.venv\Scripts\python.exe -m alembic upgrade head
# 3. restart uvicorn
```

Rollback:

```powershell
.\.venv\Scripts\python.exe -m alembic downgrade -1
```

(The initial migration `26be4ceea8b2_initial_schema` is the only one so far; downgrade
therefore drops to an empty schema — restore the backup for real rollbacks.)

## 7. Verified: full quality gate (run before every deploy)

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q          # 112 passed, 5 skipped (opt-in live)
.\.venv\Scripts\python.exe -m ruff check app tests alembic
.\.venv\Scripts\python.exe -m ruff format --check app tests alembic
.\.venv\Scripts\python.exe -m mypy app tests --ignore-missing-imports

cd ..\frontend
npm run test                                            # 21 passed
npm run lint                                            # oxlint exit 0
npm run typecheck                                       # strict TS
npm run build                                           # production bundle
```

Live provider tests (optional, costs real tokens):

```powershell
cd backend
$env:SHEETJEDI_LIVE_TESTS = "1"
$env:GROQ_API_KEY = "..."     # and/or OPENROUTER_/OPENAI_/ANTHROPIC_/LONGCAT_API_KEY
.\.venv\Scripts\python.exe -m pytest -m live -q
```

## 8. UNVERIFIED: background services & containers

These steps could not be executed here (no Docker; service managers not configured in this
sandbox). They are provided as starting points and must be tested on your target host.

### 8a. Docker (unverified — Docker not installed here)

```dockerfile
# backend/Dockerfile (sketch — NOT executed/verified in this build)
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install .            # runtime deps only (dev extras omitted)
RUN alembic upgrade head
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml (sketch — NOT executed/verified in this build)
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      SHEETJEDI_ENV: production
      SHEETJEDI_SECRET_KEY: ${SHEETJEDI_SECRET_KEY}
      SHEETJEDI_DATABASE_URL: sqlite:////data/sheetjedi.db
    volumes: ["sheetjedi-data:/data"]
volumes:
  sheetjedi-data:
```

### 8b. Windows scheduled task (unverified)

```powershell
# Sketch — not executed in this environment
$action = New-ScheduledTaskAction -Execute "C:\path\to\backend\.venv\Scripts\python.exe" `
  -Argument "-m uvicorn app.main:app --host 127.0.0.1 --port 8000" -WorkingDirectory "C:\path\to\backend"
$trigger = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName "sheetJEDI" -Action $action -Trigger $trigger -RunLevel Limited
```

### 8c. Linux systemd unit (unverified)

```ini
# /etc/systemd/system/sheetjedi.service (sketch — NOT executed in this environment)
[Unit]
Description=sheetJEDI
After=network.target

[Service]
WorkingDirectory=/opt/sheetJEDI/backend
Environment=SHEETJEDI_ENV=production
Environment=SHEETJEDI_SECRET_KEY=<fernet key>
ExecStart=/opt/sheetJEDI/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## 9. Post-deploy smoke checklist

1. `GET /api/v1/health` → `status: ok`
2. `GET /api/v1/ready` → database ok
3. `GET /` → SPA loads, footer shows author credits
4. Settings → paste a key → Save → **Test connection** → expect an *honest* result
   (success only when the provider really accepts the key; a wrong key must fail — verified
   live with an intentionally invalid Groq key → “groq: authentication failed”)
5. Workspace → generate a request without any provider → structured, friendly error with a
   request ID (verified)
6. Analyzer → consent + CSV → profile appears, temp file note shown (verified)
7. Confirm `.env` is not web-accessible and `data/` is backed up
