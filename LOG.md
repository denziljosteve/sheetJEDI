# sheetJEDI — Development Log

Chronological record of meaningful development activity. Failures and blockers
are recorded honestly; no secrets are ever included.

---

## 2026-10-28 — Session 1: Discovery, foundation, backend complete

### Discovery
- Repository was **empty** (no existing code to preserve); `git init` executed.
- Environment: Windows 11, Python 3.14.4 (default) + **Python 3.12** via `py`
  launcher (chosen for ecosystem stability), Node v24.15.0, npm 12.0.2,
  Git 2.54. **Docker is not installed** in this environment.
- npm registry reachable; PyPI reachable.
- Provider documentation research (see decision.md D-003):
  - Groq `api.groq.com/openai/v1` → 401 unauth (exists), OpenAI-compatible.
  - OpenRouter `openrouter.ai/api/v1` → 200 on public `/models`.
  - OpenAI `api.openai.com/v1` → 401 unauth (exists).
  - Anthropic `api.anthropic.com/v1` → 401 unauth (exists), Messages API.
  - OmniRoute → open-source **self-hosted** AI gateway
    (github.com/NFTHiKe/OmniRoute), OpenAI-compatible API; requires
    user-provided base URL. Marked `protocol_verified_host_required`.
  - LongCat (Meituan) → Anthropic-compatible endpoint at
    `https://api.longcat.chat/anthropic` verified reachable (401 unauth;
    OpenAI-style path 404s). Model IDs discovered dynamically at runtime.

### Milestone 1 — Foundation + backend (complete)
- Backend scaffolded: FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + httpx
  + cryptography + openpyxl + pandas, Python 3.12 venv at `backend/.venv`.
- Created `pyproject.toml` with ruff/mypy/pytest config.
- Core modules: `config.py` (pydantic-settings, `SHEETJEDI_` prefix),
  `logging.py` (secret redaction filter), `errors.py` (consistent error
  envelope), `security.py` (Fernet encryption + master key handling),
  `ratelimit.py` (in-memory sliding window).
- DB layer: 4 tables (`provider_configs`, `solutions`, `files`,
  `app_settings`), SQLite default / Postgres-ready, Alembic initial migration
  generated **and verified** (`alembic upgrade head` on a fresh DB created all
  tables).
- Provider layer: `ProviderAdapter` interface + `OpenAIChatAdapter`
  (Groq/OpenRouter/OpenAI/OmniRoute) + `AnthropicMessagesAdapter`
  (Anthropic/LongCat) + registry + normalized provider errors
  (auth/rate-limit/timeout/malformed/truncated).
- Services: prompts (task-family + version-aware), solution parser
  (fence/prose tolerant JSON extraction, cross-field validation, one repair
  round-trip, degraded fallback), safety scanner (destructive-pattern
  warnings; never executes code), generation orchestrator (bounded transient
  retries, explicit disclosed fallback, history per privacy toggle), file
  analyzer (bounded reads, magic-byte validation, immediate temp deletion,
  expiry), history + settings services.
- API v1: health/ready, providers CRUD + models + test, solutions
  generate/stream/validate, files analyze/list/delete, history
  list/get/delete. Request-ID middleware, CORS restriction, rate limiting.

### Verification ( Milestone 1 )
- `pytest tests -q` → **111 passed, 5 skipped** (skips = opt-in live provider
  tests requiring `SHEETJEDI_LIVE_TESTS=1` + credentials).
- `ruff check app tests alembic` → clean.
- `mypy app tests` → clean (47 files).
- Alembic fresh-DB migration verified (tables: `app_settings`, `files`,
  `provider_configs`, `solutions`).
- Real server boot (`uvicorn app.main:app --port 8000`) verified:
  `GET /api/v1/health` → ok, `GET /api/v1/ready` → database ok,
  `GET /api/v1/providers` → 6 providers, malformed POST → structured 422
  envelope with request ID.

### Bugs found & fixed during development
1. `/files/{id}` route duplicated the router prefix (`/files/files/{id}`) —
   caught by `test_delete_file_analysis`; fixed route paths.
2. `re.error` (global flags not at start) in a safety regex with a mid-pattern
   `(?i)` — Python 3.12 rejects this; regex rewritten; caught by tests.
3. Office Scripts `.delete(...)` pattern didn't match plain `delete()` calls —
   fixed pattern; caught by tests.
4. Degraded solutions built with `model_construct` re-triggered cross-field
   validation (formula tasks require formula/code) — degraded path now carries
   the raw output in `code` with `code_language="unvalidated_output"`.
5. Two test-side issues (Windows timer granularity in limiter test; naive
   `'api_key' not in text` assertion matching `api_key_hint`) — tests fixed.

### Next
- Frontend implementation (Vite + React + TS + Tailwind): design system,
  workspace, generators, analyzer, history, settings pages; Vitest + RTL.
- End-to-end wiring against the live backend; docs (README, flow, deploy).

---

## 2026-10-28 — Session 2: Frontend complete, integration verified, docs

### Milestone 2 — Frontend (complete)

- Design system on Tailwind v4 CSS-first tokens (light default + dark toggle):
  Button/Field/Card/Badge/Dialog/Skeleton/Toast + `CopyButton` + `AppShell`
  (skip-link, desktop + mobile nav, theme toggle with `aria-pressed`,
  footer with full author credits from a single `lib/credits.ts` source).
- **Workspace**: `WorkspaceForm` (React Hook Form + Zod resolver) with
  request textarea + char counter, example chips, platform/task/skill/language,
  conditional Excel-version field, **dynamic task-specific guided fields**,
  collapsible spreadsheet context (9 fields), provider/model/fallback section
  (explicit disclosure copy), optional workbook attachment + per-request consent
  checkbox. `SolutionView` renders the full solution schema (formula block +
  Monaco code block + steps + alternatives + warnings + common errors +
  troubleshooting + confidence) with copy controls and transparency notices
  (fallback used / degraded). Monaco loads from CDN with a **plain `<pre>`
  fallback** if the loader fails; tests stub it.
- **Pages**: Home (presets, features, live provider status strip, credits),
  Workspace (`/generate/:preset`), File Analyzer (consent-gated upload,
  recommendations, column profiles, sample preview, attach-to-workspace),
  History (+ detail, delete-with-dialog), Settings (per-provider key/base-URL/
  model/timeout + Save/Test, masked hints, app defaults, security notes),
  About (author, principles, stack, honest verification table), NotFound.
- API client mirrors the error envelope onto `ApiError` (code/status/details/
  request_id); TanStack Query hooks with sensible retry policy; friendly
  client-side hints layered over server messages.

### Verification ( Milestone 2 )
- `npm run typecheck` (tsc strict) → clean.
- `npm run lint` (oxlint) → **exit 0** (4 advisory react-compiler warnings,
  accepted: RHF `watch` incompatibility note +3× “setState in effect” for
  syncing server state into form fields — see decision D-014).
- `npm test` → **21 passed** across 5 files (SolutionView render/copy/fallback
  notices, WorkspaceForm dynamic guided fields + example fill + validation +
  context submit, Settings key masking + save + honest test failure + adapter
  status, API error mapping, app navigation/theme/mobile/404 smoke).
- `npm run build` → `tsc -b && vite build` OK (511 kB JS / 156 kB gzip;
  chunk-size warning noted as future code-splitting work).

### Integration verification (real browser + real backend)
Ran `uvicorn` (127.0.0.1:8000) + `vite` dev server and drove the UI in a real
Chromium tab:
1. Home: all 9 presets, live `GET /providers` → “0 of 6 configured”, honest
   protocol statuses (incl. OmniRoute `protocol_verified_host_required`),
   **zero console errors**.
2. Workspace: submit without providers → `POST /solutions/generate` 400 →
   structured envelope → friendly UI error **with request ID**, no page reload.
3. Settings: pasted an intentionally invalid Groq key → Save → input cleared,
   placeholder became `Stored: ••••test — leave blank to keep`, raw key absent
   from DOM → **Test connection** → live call
   `GET https://api.groq.com/openai/v1/models → 401` → UI showed
   “Connection failed — groq: authentication failed. Check the API key…”.
   Key then removed (status back to `unconfigured`) to leave the DB clean.
4. Theme toggle → `.dark` on `<html>`, persisted in localStorage.
5. Analyzer: consent + `customers.csv` → 200 in ~95 ms; duplicate row detected,
   `Amount` inferred as number, privacy notes shown.

### Backend changes in Session 2
- **Bug6 (crash):** SPA catch-all route annotated `FileResponse | JSONResponse`
  crashed `create_app()` under current FastAPI *once `frontend/dist` existed*
  (Session-1 boot had no dist → block skipped). Fixed with
  `response_model=None`; regression test `tests/test_spa_serving.py` added
  (index + SPA fallback + assets + traversal guard + JSON API 404).
- **Bug7 (cosmetic data leak):** CSV/TXT analyses labelled sheets with the
  *temp file* name (`tmpw14b02eu`) because `_analyze_text` used `path.stem` of
  the private temp file. Fixed to use the sanitized original filename; two
  assertions added in `tests/test_files.py`; re-verified in the live UI
  (sheet now `customers`).
- Applied `ruff format` across `app tests alembic` (17 files) so the codebase
  is uniformly formatted; re-ran all gates.

### Final gate results (Session 2)
| Gate | Result |
|---|---|
| `pytest tests -q` | **112 passed, 5 skipped** (live opt-in) |
| `ruff check` / `ruff format --check` | clean / clean |
| `mypy app tests` | clean (48 files) |
| `npm test` | **21 passed** |
| `npm run lint` | exit 0 (4 advisory warnings) |
| `npm run typecheck` | clean |
| `npm run build` | OK |
| Live browser integration | verified (see above) |

### Honest limitations recorded in Session 2
- **No API keys** exist here, so no authenticated generation ever ran; only the
  *failure* path of a live provider call was observed (401 with invalid key —
  exactly the truthful behavior required).
- OmniRoute remains untestable without a user-hosted instance.
- Docker/systemd/nginx/Postgres steps remain unexecuted (marked ⚠️ in
  deploy.md / PRODUCTIONDEPLOY.md).
- Playwright e2e: attempt in progress at time of writing (browser install
  kicked off); status recorded in PROGRESS.md after it completes.

### Bugs found & fixed during frontend work
1. `CopyButton` initially written to a garbage nested path (`Copilot components/…`)
   by a bad tool-call path; removed the stray tree and created the file at
   `src/components/CopyButton.tsx` (verified by listing).
2. `Card` dropped unknown props (e.g. `data-testid`) — component now spreads
   `HTMLAttributes<HTMLDivElement>` (caught by failing tests).
3. `@monaco-editor/react` has no `fallback` prop (type error) — replaced with a
   `loader.init()` timeout → plain `<pre>` fallback, which also keeps the code
   visible offline.
4. `stubFetch` matched `/providers` before `/providers/{p}/test` — helpers now
   match longest pattern first (test-infra bug, would have masked failures).
5. Test assertion issues (asymmetric matcher in `toHaveValue`, case-sensitive
   `toContain`, missing optional `code` field in fixture) — fixed.

---

## Session 2 addendum � e2e, audit, git (2026-10-28)

### Playwright e2e (first run + fix)
- First run: **3 passed, 1 failed.** Failure was in the *test*, not the app:
  the consent assertion parsed the multipart body as `consent=true`, but
  multipart parts are `Content-Disposition: form-data; name="consent"` +
  blank line + `true`. Fixed the matcher to
  `/name="consent"\r?\n\r?\ntrue/`.
- Re-run: **4/4 passed** (3.1s). Re-verified again after the audit upgrade:
  **4/4 passed**. Coverage: mocked happy-path generation + payload contract,
  structured error with request ID, analyzer consent gating, dark-theme
  persistence across reload. Entire `/api/v1` surface mocked in-browser �
  no backend, no keys, no paid calls.

### npm audit
- Initial: **2 moderate** (vitest / @vitest/mocker advisories, dev-only).
  `npm audit fix` upgraded 8 packages ? **0 vulnerabilities**.
- Post-upgrade gates re-run: 21/21 Vitest, typecheck clean, build OK,
  e2e 4/4 � no regressions.

### Final gate matrix (post-everything)
| Gate | Result |
|---|---|
| `pytest tests -q` | 112 passed, 5 skipped |
| `ruff check app tests alembic` | clean |
| `ruff format --check app tests alembic` | clean (49 files) |
| `mypy app tests --ignore-missing-imports` | clean (48 files) |
| `npm run typecheck` | clean (strict) |
| `npm test` | 21 passed |
| `npm run lint` | exit 0 (4 advisory warnings) |
| `npm run build` | OK (511 kB JS / 156 kB gzip) |
| `npx playwright test` | 4 passed |
| `npm audit` | 0 vulnerabilities |

### Git
- `git init` + author (Denzil Josteve Fernandes / denziljosteve@gmail.com).
- `.gitignore` verified with `git check-ignore` (backend/.env, .venv/,
  backend/data/, frontend/dist/ all ignored).
- 4 commits on `master`: scaffolding ? backend ? frontend (incl. e2e) ? docs.
- Secret scan over tracked files: only fake fixtures used by redaction tests.
- Working tree clean after commits.
