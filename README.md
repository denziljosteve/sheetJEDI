# sheetJEDI

**AI copilot for Excel & Google Sheets** — turn plain English into formulas, VBA macros,
Office Scripts, Google Apps Script, data-cleaning steps, analysis and reporting solutions,
with six AI providers behind one honest, privacy-respecting workflow.

> Built by **Denzil Josteve Fernandes** ·
> [denziljosteve@gmail.com](mailto:denziljosteve@gmail.com) ·
> [LinkedIn](https://www.linkedin.com/in/denziljosteve/) ·
> [Portfolio](https://denziljosteve.github.io/) ·
> [GitHub](https://github.com/denziljosteve/)

---

## What it does

| Capability | Details |
|---|---|
| **Formula engine** | XLOOKUP, INDEX/MATCH, SUMIFS, ARRAYFORMULA, dynamic arrays — version-aware (Microsoft 365 vs Excel 2016 vs Google Sheets) |
| **Code generation** | VBA macros, Office Scripts (TypeScript), Google Apps Script with placement instructions |
| **Cleaning / analysis / reporting** | Dedup, standardisation, pivots, summaries, recurring reports, chart guidance |
| **Troubleshooting** | #REF!, #VALUE!, #N/A, SUMIFS #VALUE!, VBA runtime errors — diagnosis + fix |
| **Structured output** | Every solution: title, summary, explanation, step-by-step instructions, formula/code, assumptions, alternatives, common errors, **warnings**, confidence notes |
| **File Analyzer** | Local profiling of .xlsx/.xlsm/.csv/.txt — headers, inferred types, samples, duplicates, cleaning recommendations |
| **6 providers** | Groq, OpenRouter, OpenAI, Anthropic, OmniRoute, LongCat — one abstraction, explicit disclosed fallback |
| **History** | Local-only, per-request toggle, delete any time |

### Privacy & safety (by design)

- API keys are **encrypted at rest (Fernet)** and never returned to the browser or written to
  logs — only a masked hint like `••••7890` is ever displayed.
- **Generated code is never executed** by sheetJEDI. You review, you run.
- Destructive patterns (clearing sheets, deleting ranges, sending data) are flagged as
  warnings in the generated solution.
- Workbook uploads are validated (extension, size, magic bytes), analysed **locally**, and the
  file content is **deleted immediately**; only a structured profile remains. Sending workbook
  context to an AI provider requires a **separate, explicit per-request consent**.
- Retries apply only to transient failures (429/5xx/timeouts) and are bounded.
- When a fallback provider answers, the result is labelled **“Fallback used”**. When schema
  validation degrades, you see a **degraded notice** — never a silent failure.

## Architecture (short)

```
React 19 + TS + Tailwind v4 + Monaco        FastAPI + Pydantic + SQLAlchemy + Alembic
        │  /api/v1 (fetch, TanStack Query)             │
        └──────────────►  Vite dev proxy  ─────────────┤
                        or built SPA served by FastAPI │
                                                       ▼
                              SQLite (default)  ·  provider adapters (OpenAI-compat + Anthropic)
                                                       ▼
                              Groq · OpenRouter · OpenAI · Anthropic · OmniRoute · LongCat
```

Full details, diagrams and data flows: **[flow.md](flow.md)**.

## Quickstart (verified on Windows, Python 3.12, Node 24)

### 1. Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m alembic upgrade head     # creates data/sheetjedi.db + tables
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health check: `GET http://127.0.0.1:8000/api/v1/health` → `{"status":"ok","version":"0.1.0"}`

### 2. Frontend (dev)

```powershell
cd frontend
npm install
npm run dev          # http://localhost:5173  (proxies /api → 127.0.0.1:8000)
```

### 3. Single-process production build (verified)

```powershell
cd frontend && npm run build          # emits frontend/dist
cd ../backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# FastAPI serves frontend/dist with SPA fallback → everything on one port
```

### 4. Configure a provider

Open **Settings** → pick a provider → paste an API key → **Save** → **Test connection**.
Keys are stored encrypted; the UI shows only a masked hint afterwards.

No account system: the app binds to `127.0.0.1` (see `decision.md` D-007).

## Provider verification status (honest)

| Provider | Endpoint | Protocol | Verification status |
|---|---|---|---|
| Groq | `https://api.groq.com/openai/v1` | OpenAI-compatible | `protocol_verified` + **live-reached** (401 with invalid key during UI verification, 2026-10-28) |
| OpenRouter | `https://openrouter.ai/api/v1` | OpenAI-compatible | `protocol_verified` (public `/models` → 200 during discovery) |
| OpenAI | `https://api.openai.com/v1` | OpenAI-compatible | `protocol_verified` (401 unauth during discovery) |
| Anthropic | `https://api.anthropic.com` | Messages API | `protocol_verified` (401 unauth during discovery) |
| OmniRoute | user-provided base URL | OpenAI-compatible (self-hosted gateway) | `protocol_verified_host_required` — **cannot be tested without your own instance** |
| LongCat | `https://api.longcat.chat/anthropic` | Anthropic-compatible | `protocol_verified` (401 unauth; OpenAI-style path 404s) |

**No API keys existed in the build environment**, so successful authenticated generation calls
were **not** run there. The opt-in live suite does exactly that when you provide credentials:

```powershell
$env:SHEETJEDI_LIVE_TESTS = "1"
$env:GROQ_API_KEY = "gsk_..."          # any subset of the six
.\.venv\Scripts\python.exe -m pytest -m live -q
```

CI never needs paid calls; live tests skip unless explicitly enabled with credentials.

## API surface (`/api/v1`)

| Method & path | Purpose |
|---|---|
| `GET /health`, `GET /ready` | Liveness / readiness (DB check) |
| `GET /providers`, `GET /providers/{p}/models`, `POST /providers/{p}/test` | Provider status, model discovery (TTL cache), live connection test |
| `PUT /settings/providers/{p}`, `GET|PUT /settings/app` | Encrypted key/config storage, app defaults |
| `POST /solutions/generate` | Full lifecycle: validate → generate → repair → fallback → history |
| `POST /solutions/stream` | SSE streaming (primary provider only — see `decision.md` D-009) |
| `POST /files/analyze`, `DELETE /files/{id}` | Local workbook profiling (consent required) |
| `GET /history`, `GET /history/{id}`, `DELETE /history/{id}` | Local generation history |

Errors always follow the envelope:

```json
{ "error": { "code": "rate_limited", "message": "...", "details": {}, "request_id": "..." } }
```

## Testing & code quality (all commands verified)

```powershell
# Backend — 112 passed, 5 skipped (live, opt-in)
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m ruff check app tests alembic
.\.venv\Scripts\python.exe -m ruff format --check app tests alembic
.\.venv\Scripts\python.exe -m mypy app tests --ignore-missing-imports

# Frontend — 21 passed (Vitest + React Testing Library)
cd frontend
npm run test         # vitest run
npm run lint         # oxlint (exit 0; 4 advisory react-compiler warnings, see LOG.md)
npm run typecheck    # tsc -b --noEmit (strict)
npm run build        # tsc -b && vite build
```

Live provider tests are **opt-in only**: `SHEETJEDI_LIVE_TESTS=1` + credentials.

## Project structure

```
sheetJEDI/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # routers: health, providers, solutions, files, history
│   │   ├── core/            # config, logging+redaction, errors, security (Fernet), ratelimit
│   │   ├── db/              # SQLAlchemy models (4 tables) + session
│   │   ├── providers/       # adapter interface, OpenAI-compat + Anthropic adapters, registry
│   │   └── services/        # prompts, solution parser, safety, generation, files, settings
│   ├── alembic/             # migrations (initial: 26be4ceea8b2)
│   └── tests/               # 117 tests incl. opt-in live suite (tests/live/)
├── frontend/
│   └── src/
│       ├── components/      # ui kit, layout, workspace (form, solution view, code block)
│       ├── pages/           # Home, Workspace, Analyzer, History, Settings, About
│       ├── lib/             # api client, queries, types, constants, credits
│       └── test/            # vitest setup + helpers
├── README.md  flow.md  deploy.md  PRODUCTIONDEPLOY.md
├── LOG.md  PROGRESS.md  decision.md
└── .env.example  .gitignore  LICENSE
```

## Documentation

| Document | Contents |
|---|---|
| [flow.md](flow.md) | Architecture & data-flow diagrams (Mermaid), request lifecycle |
| [deploy.md](deploy.md) | Verified deployment commands (local, single-port, Windows service notes) |
| [PRODUCTIONDEPLOY.md](PRODUCTIONDEPLOY.md) | Production checklist: secrets, reverse proxy, TLS, backups, monitoring |
| [decision.md](decision.md) | Decision log D-001…D-009, A-001 (assumptions) |
| [LOG.md](LOG.md) | Chronological development log incl. bugs found & fixes |
| [PROGRESS.md](PROGRESS.md) | Progress dashboard, test/build status matrix |

## License

MIT — see [LICENSE](LICENSE). Copyright © 2026 Denzil Josteve Fernandes.
