# sheetJEDI — Progress Dashboard

**Last updated:** 2026-10-28 (Session 2 — feature-complete, all local gates green)

## Current phase
Phase 7 — Verification & documentation (Phases 1–6 complete and verified).

## Completed
- [x] Repository discovery (empty repo; toolchain verified: Python 3.12, Node 24, no Docker)
- [x] Provider documentation research for all six providers (endpoints verified reachable)
- [x] Backend foundation: FastAPI app, config, logging w/ secret redaction, error envelope,
      rate limiting, request IDs, CORS restriction
- [x] Persistence: SQLAlchemy models (4 tables), SQLite default / Postgres-ready, Alembic
      initial migration (verified on fresh DB)
- [x] Security: Fernet-encrypted API key storage, masked hints, master key handling,
      production requires `SHEETJEDI_SECRET_KEY`
- [x] Provider layer: interface + OpenAIChatAdapter (Groq, OpenRouter, OpenAI, OmniRoute)
      + AnthropicMessagesAdapter (Anthropic, LongCat) + normalized errors + model discovery
      with TTL cache + real connection tests
- [x] Generation engine: task-family prompts, version-aware rules, JSON contract, parser
      (fence/prose tolerant), cross-field validation, one repair round-trip, degraded
      fallback, destructive-pattern safety scan, explicit disclosed fallback, history
- [x] File analysis: .xlsx/.xlsm/.csv/.txt, magic-byte + size validation, bounded row scan,
      type inference, duplicate/blank detection, recommendations, immediate temp deletion,
      expiry purge
- [x] API v1 endpoints: health, ready, providers (+models/test/settings), solutions
      (generate/stream/validate), files (analyze/list/delete), history (list/get/delete)
- [x] **Frontend (Vite + React + TS + Tailwind v4 + RHF + Zod + TanStack Query + React
      Router):** AppShell (skip link, responsive nav, dark toggle, credits footer),
      Workspace/Formula/VBA/Apps Script/Office Script/Cleaning pages with guided fields +
      examples + consent, Monaco CodeBlock with plain `<pre>` fallback, SolutionView,
      Analyzer, History + detail, Settings (keys masked, test-connection), About/author,
      NotFound
- [x] Frontend tests (Vitest + RTL): **21 passed**; typecheck clean; production build OK
- [x] Live browser integration verified (real Chromium + real backend + Vite dev server):
      zero console errors, honest provider statuses, error envelope with request ID,
      **real Groq connection-test call returned 401** (invalid key → truthful failure),
      theme persistence, analyzer CSV flow
- [x] **Playwright e2e (fully mocked /api/v1, no backend, no keys): 4/4 passed**
- [x] Docs: README.md, LOG.md, PROGRESS.md, decision.md (D-001…D-014, A-001), flow.md
      (6 Mermaid diagrams), deploy.md, PRODUCTIONDEPLOY.md, LICENSE (MIT)
- [x] Security review (recorded in LOG.md Session 2): secrets never echoed, `.env`
      git-ignored (verified with `git check-ignore`), consent gating, temp-file deletion,
      no auto-execution of generated code, destructive-pattern warnings

## In progress
- [ ] Git: repository initialized + author configured + `.gitignore` verified;
      initial commit pending (no commits yet at time of writing).

## Blocked / pending verification
- **Live provider success paths:** no API keys available in this environment. Only the
  *failure* path was observed live (Groq HTTP 401 with an intentionally invalid key).
  Live suite exists (`backend/tests/live/`, `pytest -m live`) gated behind
  `SHEETJEDI_LIVE_TESTS=1` + provider keys.
- **OmniRoute:** requires a user-hosted instance; adapter implemented to its
  OpenAI-compatible protocol, connection inherently untestable here.
- **Docker / systemd / nginx / Postgres:** not installed/configured in this environment;
  snippets provided but marked ⚠️ unverified everywhere they appear.
- **@playwright/test audit notice:** npm reported a low-severity advisory chain during
  install — `npm audit` to be run and reported honestly.

## Test & build status
| Check | Command | Status |
|---|---|---|
| Backend unit/integration | `cd backend; pytest tests -q` | ✅ 112 passed, 5 skipped (live, opt-in) |
| Backend lint | `ruff check app tests alembic` | ✅ clean |
| Backend format | `ruff format --check app tests alembic` | ✅ clean |
| Backend types | `mypy app tests --ignore-missing-imports` | ✅ clean (48 files) |
| Alembic migration | `alembic upgrade head` (fresh DB) | ✅ verified |
| Server boot | `uvicorn app.main:app` | ✅ health/ready/providers verified |
| Frontend typecheck | `npm run typecheck` | ✅ clean (strict) |
| Frontend tests | `npm test` (Vitest + RTL) | ✅ 21 passed |
| Frontend lint | `npm run lint` (oxlint) | ✅ exit 0 (4 advisory warnings) |
| Frontend build | `npm run build` | ✅ OK (511 kB JS / 156 kB gzip) |
| e2e (mocked API) | `npx playwright test` | ✅ 4 passed (Chromium) |
| Live browser integration | manual (Chromium + backend + Vite) | ✅ verified, 0 console errors |
| Live provider suite | `pytest -m live` | ⏸ skipped without `SHEETJEDI_LIVE_TESTS=1` |

## Known issues / accepted limitations
- Chunk-size warning on production build (511 kB > 500 kB advisory) — future
  code-splitting work; not a defect.
- oxlint advisory warnings (4): RHF `watch` compiler note + 3× setState-in-effect used
  deliberately for server→form sync; reviewed, not bugs.
- Streaming endpoint: primary provider only (no fallback/repair) — by design (D-009).

## Next steps
1. Git initial commit (incremental groups), verifying no secrets are staged.
2. Final gate re-run + `npm audit` report.
3. Final report with verified vs. unverified evidence.
