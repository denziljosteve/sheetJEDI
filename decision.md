# sheetJEDI — Decision Log

Architecture Decision Records for sheetJEDI. Each decision records context,
alternatives, the chosen option, trade-offs, risks, and revisit conditions.

---

## D-001 — Local-first architecture with SQLite default

- **Date:** 2026-10-28
- **Status:** Accepted
- **Context:** sheetJEDI is a personal productivity tool in its first release.
  Persistent multi-user data is not yet required, and the target deployment is
  a single user on their own machine.
- **Alternatives:**
  1. PostgreSQL from day one (spec's "when data requires it" path).
  2. File-based JSON store only (no SQL layer).
  3. SQLAlchemy + SQLite by default, PostgreSQL via a single env var.
- **Decision:** Option 3. SQLAlchemy 2.x models with Alembic migrations; the
  database URL comes from `SHEETJEDI_DATABASE_URL` (default
  `sqlite:///./data/sheetjedi.db`). The `postgres` extra installs `psycopg`.
- **Trade-offs:** No multi-user auth/row-level security (not needed yet).
  SQLite is single-writer (fine for one user). Migrations must be verified
  against PostgreSQL before any hosted multi-user deployment.
- **Risks:** A later multi-user move needs auth + ownership checks + Postgres
  migration testing; all schema changes must go through Alembic.
- **Revisit when:** multi-user hosting, auth, or concurrent writers are needed.

## D-002 — API key storage: Fernet encryption in the local database

- **Date:** 2026-10-28
- **Status:** Accepted
- **Context:** Provider API keys must be stored so the backend can call
  providers, but must never reach the browser or logs.
- **Alternatives:**
  1. Plain `.env` files only (no in-app editing).
  2. OS keychain integration (e.g. `keyring`).
  3. Fernet-encrypted values in the local DB, master key from
     `SHEETJEDI_SECRET_KEY` (dev fallback: generated `data/.master_key`).
- **Decision:** Option 3 via the `cryptography` package (AES-128-CBC +
  HMAC-SHA256 — an established mechanism, not homemade crypto). Keys are
  decrypted server-side only; the API returns a masked hint (`••••1234`).
  `SHEETJEDI_SECRET_KEY` is required in production.
- **Trade-offs:** DB theft alone does not reveal keys (without the master
  key), but a machine-level attacker with both DB and master key wins. An OS
  keychain adds platform complexity; documented as a possible upgrade.
- **Risks:** Losing the master key makes stored credentials unrecoverable
  (user must re-enter keys; surfaced with a clear error).
- **Revisit when:** a multi-user or hosted deployment needs per-user isolation
  (see PRODUCTIONDEPLOY.md for KMS-backed approaches).

## D-003 — Provider abstraction: two protocol adapters, six providers

- **Date:** 2026-10-28
- **Status:** Accepted
- **Context:** Six providers were requested. Research (2026-10-28) established:
  - Groq, OpenRouter, OpenAI expose OpenAI-compatible chat APIs
    (endpoints verified reachable: 401 without auth; OpenRouter's public
    `/models` returned 200).
  - Anthropic uses its own Messages API (`x-api-key`, `anthropic-version`,
    system prompt outside messages, required `max_tokens`).
  - OmniRoute is an open-source *self-hosted* AI gateway
    (github.com/NFTHiKe/OmniRoute) exposing OpenAI-compatible APIs — it has no
    single official hosted endpoint, so a configurable base URL is required.
  - LongCat (Meituan) exposes an **Anthropic-compatible** endpoint at
    `https://api.longcat.chat/anthropic` (verified reachable: 401 without
    auth; the OpenAI-style path `/v1/models` 404s). Models include
    `LongCat-2.5-Preview` and `LongCat-2.0` per third-party integration
    configs (GCMP project).
- **Decision:** Implement `OpenAIChatAdapter` (Groq, OpenRouter, OpenAI,
  OmniRoute) and `AnthropicMessagesAdapter` (Anthropic, LongCat) behind one
  `ProviderAdapter` interface (`validate_config`, `list_models`,
  `test_connection`, `generate`, `stream`, `capabilities`,
  `normalize_error`). JSON mode is advertised only where natively supported.
- **Trade-offs:** OmniRoute/LongCat adapters are protocol-verified but not
  live-tested (no credentials/instance available in this environment); their
  status fields say exactly that. No adapter claims a working authenticated
  connection until a real test succeeds.
- **Risks:** Provider API drift; mitigated by dynamic model discovery and
  normalized error handling.
- **Revisit when:** a provider ships a materially different API (e.g. OpenAI
  Responses-only features).

## D-004 — Structured output: prompt-driven JSON + validation + one repair + degraded fallback

- **Date:** 2026-10-28
- **Status:** Accepted
- **Context:** LLM output must be converted into a typed `SolutionResponse`;
  models sometimes wrap JSON in prose/fences or return invalid JSON.
- **Decision:** System prompt defines a strict JSON contract; the parser strips
  fences/prose, validates with Pydantic (including cross-field rules), retries
  *once* feeding validation errors back, then returns a clearly-marked
  **degraded** response containing the raw output (never silently discarded,
  never silently trusted).
- **Trade-offs:** One extra round-trip on malformed output (small latency
  cost). Degraded responses are explicitly flagged in the UI.
- **Revisit when:** provider-native structured outputs (e.g. strict schemas)
  become uniformly available across the six providers.

## D-005 — File analysis: bounded local reads, no retention of file content

- **Date:** 2026-10-28
- **Status:** Accepted
- **Context:** Workbook analysis must be safe (malformed/oversized files),
  bounded (huge sheets), and privacy-preserving.
- **Decision:** `openpyxl` read-only mode for `.xlsx/.xlsm` (macros never
  loaded/executed), `csv` module for `.csv/.txt`. Up to 5,000 rows scanned per
  sheet with a `truncated` flag; temp files deleted immediately after
  analysis; only the structured analysis JSON is stored with an expiry
  (`SHEETJEDI_UPLOAD_RETENTION_MINUTES`). Sending workbook context to an AI
  provider requires explicit per-request consent (`include_file_context`).
- **Trade-offs:** Duplicate/blank statistics are computed over *scanned* rows
  only for large sheets (clearly labeled). No `.xls` support (no verified
  parser installed).
- **Risks:** openpyxl cannot evaluate formulas (cached values only) — stated
  in every analysis note; never claimed otherwise.
- **Revisit when:** adding `.xls`/`.ods` support (needs a verified parser) or
  streaming analysis for very large workbooks.

## D-006 — History & privacy defaults

- **Date:** 2026-10-28
- **Status:** Accepted
- **Context:** Generated solutions may be persisted for convenience, but the
  product principles demand explicit privacy control.
- **Decision:** History is stored locally (SQLite), can be disabled globally
  (`SHEETJEDI_HISTORY_ENABLED`) or per user (`PUT /api/v1/settings/app`
  `history_enabled`), and stores request *metadata* + the structured response.
  Spreadsheet sample data from `context.sample_data` is **not** persisted in
  history (only the request text and selectors are).
- **Trade-offs:** No cross-device sync (out of scope for local-first).
- **Revisit when:** cloud sync or sharing features are designed.

## D-007 — No authentication in v1 (bind to localhost)

- **Date:** 2026-10-28
- **Status:** Accepted
- **Context:** The app is local-first single-user; adding auth would add
  infrastructure without a deployment target that needs it.
- **Decision:** No auth layer; the server binds `127.0.0.1` by default;
  CORS is restricted to configured origins; rate limiting is applied
  in-process. Production deployment guidance (reverse proxy + auth) lives in
  PRODUCTIONDEPLOY.md.
- **Trade-offs:** Anyone with local machine access can use the app and read
  history (acceptable for a personal tool).
- **Risks:** Accidental exposure beyond localhost in production; mitigated by
  deploy docs and explicit `SHEETJEDI_HOST` opt-in.
- **Revisit when:** the app is hosted for multiple users.

## D-008 — Frontend: Vite + React + Tailwind v4, hand-rolled accessible components

- **Date:** 2026-10-28
- **Status:** Accepted
- **Context:** The spec requires React/TS/Vite/Tailwind and shadcn/ui "or an
  accessible equivalent". The shadcn CLI adds codegen tooling and version
  churn; a small, well-tested component set is easier to audit.
- **Decision:** Hand-rolled accessible components (Button, Input, Select,
  Card, Dialog, Toast, Tabs, CopyButton…) styled with Tailwind CSS v4 design
  tokens; Monaco (locally bundled, no CDN) for code display/editing; TanStack
  Query for server state; React Hook Form + Zod for forms; React Router.
- **Trade-offs:** Fewer prebuilt components than shadcn; full control and no
  codegen dependency.
- **Revisit when:** the component needs grow beyond what the small kit covers.

## D-009 — Streaming endpoint scope

- **Date:** 2026-10-28
- **Status:** Accepted
- **Context:** SSE streaming of raw model deltas conflicts with
  provider-fallback and the validation-repair round-trip (both need the full
  response before deciding).
- **Decision:** `POST /api/v1/solutions/generate` (non-streaming) is the full
  lifecycle path (retries, repair, fallback, history). `POST
  /api/v1/solutions/generate/stream` streams deltas from the *primary*
  provider only and finishes with a validated (or degraded) `done` event; on
  failure it emits an `error` event. Documented in flow.md.
- **Trade-offs:** Streaming path forgoes fallback/repair; the UI uses the
  non-streaming endpoint for full fidelity.

## D-010 — Monaco via CDN loader with a plain `<pre>` fallback

- **Date:** 2026-10-28
- **Status:** Accepted
- **Context:** `@monaco-editor/react` is heavy (~5 MB lazy chunk) and its
  `loading` prop has no "failed" state — if the CDN loader cannot run (offline,
  blocked CDN, test environment), the component would hang forever.
- **Decision:** `CodeBlock` dynamically imports the Monaco loader
  (`monaco-editor/esm/vs/loader`) with a hard `init()` timeout; on failure or
  timeout it renders a plain `<pre><code>` block that still copies fine. Unit
  tests stub `loader.init()` (see `src/test/setup.ts`) so no CDN is contacted.
- **Trade-offs:** CDN dependency for the rich editor (progressive enhancement
  only); the fallback keeps every flow usable and testable offline.

## D-011 — Analyzer → Workspace file-context hand-off via `sessionStorage`

- **Date:** 2026-10-28
- **Status:** Accepted
- **Context:** Analyzing a workbook on the File Analyzer page should let the
  user continue in the Workspace with that context, but the backend holds no
  session state (local-first, no auth) and history entries are only created on
  generation.
- **Decision:** `lib/attachment.ts` writes a small `{file_id, filename}` record
  to `sessionStorage` (cleared on tab close); the Workspace form reads it once,
  shows the attached file with a remove button, and sends `file_id` +
  `include_file_context=true` only after the user's explicit consent checkbox.
- **Trade-offs:** Hand-off is per-tab and non-persistent (intentional — no
  cross-session file references without consent).

## D-012 — Light theme is the default; dark mode is a persisted opt-in

- **Date:** 2026-10-28
- **Status:** Accepted
- **Context:** The spec asks for a light default with a dark toggle.
- **Decision:** `index.html` ships without the `dark` class; the AppShell
  toggles `document.documentElement.classList.toggle('dark')` and persists the
  choice in `localStorage` (`sheetjedi-theme`), re-applied before first paint
  via a tiny inline script to avoid a flash. The toggle exposes
  `aria-pressed`.
- **Trade-offs:** No `prefers-color-scheme` auto-detection (the explicit user
  choice always wins after the first visit).

## D-013 — Guided dynamic fields are client-defined; backend accepts free-form dicts

- **Date:** 2026-10-28
- **Status:** Accepted
- **Context:** Each task type should offer "guided dynamic fields" (e.g.
  "range", "lookup column") beyond the free-text request, but field lists are
  presentation concerns and must not require a backend round-trip.
- **Decision:** Field definitions live in `lib/constants.ts` keyed by task type,
  are rendered by `WorkspaceForm`, and are submitted as
  `guided_fields: dict[str, str]` which the Pydantic model accepts as
  free-form (values capped at 500 chars, keys pattern-checked).
- **Trade-offs:** The backend cannot validate semantic meaning of guided
  fields; it only bounds size and type.

## D-014 — Friendly client hints layered over the server error envelope

- **Date:** 2026-10-28
- **Status:** Accepted
- **Context:** The API returns a strict `{error: {code, message, details?,
  request_id}}` envelope; raw messages are developer-oriented and some codes
  (`provider_not_configured`, `rate_limited`) benefit from actionable wording.
- **Decision:** `lib/api.ts` maps known codes to a friendly `hint` shown in the
  error banner *in addition to* the server message and request ID (e.g.
  "Configure a provider in Settings → Providers"). Unknown codes fall back to
  the server message only — nothing is invented client-side.
- **Trade-offs:** Two strings shown on some errors (hint + message); acceptable
  because the request ID must stay visible for support.

## A-001 — Assumptions

- **Date:** 2026-10-28
- OmniRoute's exact hosted offering varies (self-hosted gateway projects);
  sheetJEDI treats it as "OpenAI-compatible endpoint at a user-provided base
  URL" and marks the adapter `protocol_verified_host_required`.
- LongCat API docs are behind a JS-rendered site; base URL and Anthropic
  compatibility were verified via reachable endpoints (401 unauth) and a
  maintained third-party integration config (GCMP). Model IDs are discovered
  dynamically at runtime rather than hard-coded.
- "Google Sheets version" is treated as "current" (Google updates Sheets
  continuously); the field exists for user preference but no version-specific
  gating is applied.
- Python 3.12 (installed via the `py` launcher) is the supported runtime for
  this environment; Python 3.14 was available but 3.12 was chosen for
  ecosystem stability (spec explicitly allows "another verified supported
  version").
