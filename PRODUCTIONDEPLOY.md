# sheetJEDI — Production Deployment Checklist

Hardening guide for exposing sheetJEDI beyond `localhost`. Sections are marked:

- ✅ **Verified** — executed in the build environment (commands reproduce the result)
- ⚠️ **Unverified** — correct-by-construction guidance that could **not** be executed here
  (no Docker, no public host, no TLS certificates in this environment). Test before relying
  on it.

> **Threat model reminder:** sheetJEDI v1 has **no authentication** (decision D-007) and binds
> to `127.0.0.1` by default. Do **not** expose it directly to the internet. Put it behind a
> VPN, Tailscale/loopback SSH tunnel, or an authenticating reverse proxy.

---

## 1. Secrets & key management

### ✅ Verified

```powershell
# Production refuses to start without a master key (SHEETJEDI_ENV=production).
cd backend
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
$env:SHEETJEDI_SECRET_KEY = "<printed key>"   # set as a service/OS environment variable
```

- [x] `SHEETJEDI_SECRET_KEY` set from a secrets manager / OS env — **never** a committed file
- [x] `.env` is git-ignored (verify: `git check-ignore backend\.env` → prints the path)
- [x] `data/.master_key` (dev auto-key) does not exist on production hosts
- [x] No provider API keys in environment variables or source — they live encrypted in the DB
      (Fernet) and are only entered through the Settings UI
- [x] Log redaction verified by tests (`app/core/logging.py`) — key-like values never logged

### ⚠️ Unverified (platform-specific)

- [ ] Mount secrets via your platform's store (Windows Credential Manager, systemd
      `EnvironmentFile` with `0600`, Docker secrets, Vault…)
- [ ] Rotate the master key: decrypt/re-encrypt `provider_configs.api_key_encrypted` with a
      migration script, then re-run connection tests (rotation script not yet implemented —
      treat as a manual runbook)

## 2. Network exposure

### ✅ Verified

- [x] Binds `127.0.0.1` by default (`SHEETJEDI_HOST`)
- [x] CORS restricted to configured origins (`SHEETJEDI_CORS_ORIGINS`)
- [x] In-memory sliding-window rate limit (30 req/min default) — `SHEETJEDI_RATE_LIMIT_*`
- [x] Request-ID middleware on every response (`X-Request-ID`) for support/debug correlation
- [x] Static path-traversal guard on the SPA fallback (tested in `test_spa_serving.py`)

### ⚠️ Unverified — reverse proxy with TLS (sketch)

```nginx
# NOT executed in this environment — validate on your host.
server {
    listen 443 ssl http2;
    server_name sheetjedi.example.com;
    ssl_certificate     /etc/letsencrypt/live/sheetjedi.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sheetjedi.example.com/privkey.pem;

    # optional but recommended: basic auth in front of an auth-less v1 app
    auth_basic "sheetJEDI";
    auth_basic_user_file /etc/nginx/sheetjedi.htpasswd;

    client_max_body_size 12m;          # > SHEETJEDI_MAX_UPLOAD_MB
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Request-ID $request_id;   # app keeps client id if provided
        proxy_read_timeout 120s;                     # LLM calls can be slow
        proxy_buffering off;                         # required for SSE /solutions/stream
    }
}
```

- [ ] TLS certificate issued & auto-renewal configured
- [ ] Authentication layer added (v1 has none by design)
- [ ] SSE tested through the proxy (`curl -N .../api/v1/solutions/stream`)

## 3. Data durability (SQLite default)

### ✅ Verified

- [x] Live backup = copy the file while the app runs (SQLite online backup semantics for a
      single-writer local app):

```powershell
Copy-Item backend\data\sheetjedi.db backups\sheetjedi-$(Get-Date -Format yyyyMMdd).db
```

- [x] Migrations are Alembic-managed; `alembic upgrade head` verified from empty

### ⚠️ Unverified

- [ ] Scheduled nightly backup + retention policy (Task Scheduler / cron — not configured here)
- [ ] Restore drill: copy a backup over `data/sheetjedi.db`, boot, `GET /api/v1/ready` → ok
- [ ] PostgreSQL for multi-user/host setups: set `SHEETJEDI_DATABASE_URL` and install the
      `postgres` extra (`pip install -e ".[postgres]"`); driver/DSN **not** exercised here
- [ ] Backup encryption at rest (the DB contains encrypted provider keys but plaintext
      solutions/history)

## 4. Process supervision

### ⚠️ Unverified (no service manager configured in this environment)

- [ ] Process supervisor with auto-restart (`systemd Restart=on-failure`, Windows service,
      Docker `restart: unless-stopped` — sketches in `deploy.md` §8)
- [ ] Log rotation for uvicorn stdout/stderr output (the app logs to stdout at
      `SHEETJEDI_LOG_LEVEL`; there is no built-in log file)
- [ ] Graceful shutdown on deploy (SIGTERM → in-flight request drain)

## 5. Monitoring & health

### ✅ Verified

- [x] `GET /api/v1/health` → liveness JSON (no DB touch)
- [x] `GET /api/v1/ready` → readiness incl. DB check (use for load-balancer probes)
- [x] Structured error envelope with `request_id` on every failure — supports ticket triage

### ⚠️ Unverified

- [ ] External uptime probe on `/api/v1/ready` (5xx budget/alerting)
- [ ] Log shipping of `request_id` ↔ provider latency/usage fields for cost dashboards

## 6. Provider & cost controls

- [x] ✅ Rate limiting per client (verified by tests)
- [x] ✅ Bounded retries **only** for transient errors (429/5xx/timeout) — no retry storms
- [x] ✅ Fallback is explicit and disclosed in the UI (`fallback_used` badge)
- [x] ✅ Model discovery cached with TTL (`SHEETJEDI_MODEL_CACHE_TTL_SECONDS`) to avoid
      hammering provider `/models` endpoints
- [ ] ⚠️ Per-provider monthly spend caps — **not implemented**; use provider-side limits
      (Groq/OpenAI/OpenRouter dashboards) or a spending-cap proxy in front of OmniRoute
- [ ] ⚠️ Token-usage reporting beyond per-response `usage` — not implemented in v1

## 7. Privacy & compliance

- [x] ✅ Uploaded file content deleted immediately after analysis (finally-block + test)
- [x] ✅ Workbook context sent to a provider only with explicit per-request consent
- [x] ✅ History toggle (`SHEETJEDI_HISTORY_ENABLED` + UI) and per-entry delete
- [x] ✅ Generated code never executed by the app
- [ ] ⚠️ If you process personal data: add a retention job for `solutions` rows
      (`purge_expired_files` covers file analyses only) and document your lawful basis

## 8. Pre-production gate (copy/paste)

```powershell
# All must pass with zero failures before a production rollout.
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m ruff check app tests alembic
.\.venv\Scripts\python.exe -m ruff format --check app tests alembic
.\.venv\Scripts\python.exe -m mypy app tests --ignore-missing-imports
cd ..\frontend
npm run test
npm run lint
npm run typecheck
npm run build
```

Optional but recommended with real credentials (costs tokens):

```powershell
cd backend
$env:SHEETJEDI_LIVE_TESTS = "1"; $env:GROQ_API_KEY = "..."
.\.venv\Scripts\python.exe -m pytest -m live -q
```

## 9. Rollback plan

1. Stop the service.
2. Restore `data/sheetjedi.db` from the pre-deploy backup.
3. `alembic downgrade -1` (or redeploy the previous git tag).
4. Redeploy previous `frontend/dist` + backend code.
5. `GET /api/v1/ready` → ok, then spot-check Settings (provider hints intact = keys intact).

---

### Honest status summary

| Area | Status |
|---|---|
| App-level security controls (encryption, redaction, consent, rate limit, traversal guard) | ✅ verified by tests & live UI checks |
| Single-port production build (SPA served by FastAPI) | ✅ verified |
| Live provider **success** paths (authenticated generations) | ⚠️ not run here — no API keys; use the opt-in `live` suite |
| Docker / systemd / nginx / TLS / Postgres | ⚠️ unverified in this environment |
| Backup automation, spend caps, key rotation runbook | ⚠️ not implemented / manual |
