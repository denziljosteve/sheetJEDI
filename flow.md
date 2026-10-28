# sheetJEDI — System & Data Flow

Companion to [README.md](README.md). Diagrams use Mermaid (renders on GitHub, VS Code,
Typora, etc.). All claims here are backed by tests listed in [PROGRESS.md](PROGRESS.md).

---

## 1. Component overview

```mermaid
flowchart LR
    subgraph Client["Browser (localhost)"]
        UI["React 19 + TypeScript<br/>Tailwind v4 · RHF + Zod · TanStack Query<br/>Monaco (CDN, plain fallback)"]
        LS["localStorage<br/>theme only"]
    end

    subgraph Server["FastAPI (Python 3.12, 127.0.0.1:8000)"]
        API["/api/v1 routers<br/>+ request-ID, rate limit, CORS"]
        GEN["generation orchestrator<br/>retries · fallback · repair · history"]
        PARSE["solution parser<br/>JSON extract + schema validation"]
        SAFE["safety scanner<br/>destructive-pattern warnings"]
        FILES["file analyzer<br/>validate → temp → profile → delete"]
        SEC["security<br/>Fernet encrypt/decrypt · redaction"]
    end

    subgraph Storage["Local storage"]
        DB[("SQLite (default) / Postgres<br/>provider_configs · solutions<br/>files · app_settings")]
        ENV[("Master key<br/>SHEETJEDI_SECRET_KEY / keyfile")]
    end

    subgraph Providers["AI providers"]
        G["Groq · OpenRouter · OpenAI<br/>(OpenAI-compatible adapter)"]
        A["Anthropic · LongCat<br/>(Messages adapter)"]
        O["OmniRoute<br/>(self-hosted base URL)"]
    end

    UI -- "fetch /api/v1" --> API
    UI --- LS
    API --> GEN
    API --> FILES
    GEN --> PARSE
    GEN --> SAFE
    GEN --> SEC
    SEC --- ENV
    GEN --> DB
    FILES --> DB
    GEN --> G
    GEN --> A
    GEN --> O
```

## 2. Generation request lifecycle (non-streaming — the full path)

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant F as WorkspaceForm (RHF+Zod)
    participant A as POST /solutions/generate
    participant G as Orchestrator
    participant P as Primary provider
    participant R as Fallback provider
    participant S as SQLite (history)

    U->>F: request + platform + guided fields + consent flags
    F->>F: client validation (3–6000 chars, enums, limits)
    F->>A: GenerationRequest JSON
    A->>A: Pydantic validation + rate limit + request-ID
    A->>G: resolve provider config (decrypt key in memory)
    G->>P: chat completion (JSON contract prompt)
    alt transient failure (429 / 5xx / timeout)
        G->>P: bounded retry (only transient, fixed budget)
    end
    alt primary failed AND use_fallback AND fallback configured
        G->>R: same request (explicitly disclosed)
        Note over G: response marks fallback_used=true
    end
    G->>G: parse JSON (fence/prose tolerant)
    alt schema invalid
        G->>P: ONE repair round-trip with validation errors
        alt repair also invalid
            G->>G: degraded fallback (raw output, notice attached)
        end
    end
    G->>G: safety scan (destructive patterns → warnings)
    opt history enabled (app setting)
        G->>S: INSERT solution (request + solution + provider meta)
    end
    S-->>A: solution_id (or null)
    A-->>F: GenerationResponse (solution + meta + notices)
    F-->>U: SolutionView (copy controls, warnings, meta badges)
```

**Streaming path** (`POST /solutions/stream`, SSE): primary provider only — no fallback, no
repair round-trip; errors stream as a terminal `error` event (decision D-009).

## 3. File analysis (local-only unless consented)

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant AN as AnalyzerPage
    participant API as POST /files/analyze
    participant F as files service
    participant DB as SQLite (files table)

    U->>AN: pick file + tick "local analysis" consent
    AN->>API: multipart upload (file, consent=true)
    API->>API: consent check → 403 consent_required if missing
    API->>F: validate ext (.xlsx/.xlsm/.csv/.txt), size, magic bytes
    F->>F: write private temp file
    F->>F: profile sheets/columns (bounded row scan, type inference,<br/>duplicates, empty-heavy, recommendations)
    F->>F: DELETE temp file (finally block — content never persists)
    F->>DB: store structured analysis JSON + filename + expiry
    DB-->>U: WorkbookAnalysis (sheets, columns, samples, notes)
    Note over AN: sessionStorage holds only {file_id, filename}<br/>(no file contents)
    opt "Use in workspace"
        U->>AN: attach analysis to next request
        Note over API: workbook context is added to the prompt ONLY when<br/>include_file_context=true (explicit per-request consent)
    end
```

## 4. API key handling (never exposed, never logged)

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant S as SettingsPage
    participant API as PUT /settings/providers/{p}
    participant SEC as core.security
    participant DB as SQLite (provider_configs)
    participant LOG as log stream

    U->>S: paste key (type=password, one time)
    S->>API: {api_key} over local HTTP
    API->>SEC: encrypt_secret(key, Fernet master key)
    SEC->>DB: api_key_encrypted + api_key_hint ("••••7890")
    DB-->>API: row saved
    API-->>S: ProviderStatus WITHOUT key (only hint)
    S->>S: clears the input after confirmed save
    Note over SEC,LOG: register_secret() + redaction filter scrub<br/>key-like values from every log line
    Note over S: full key never rendered, never stored in JS state,<br/> never sent anywhere except this one PUT
```

## 5. Frontend data flow

```mermaid
flowchart TD
    R1["/  Home"] --> W["/generate/:preset  WorkspacePage"]
    R2["/analyzer"] --> AN["AnalyzerPage"]
    R3["/history  ·  /history/:id"] --> H["HistoryPage"]
    R4["/settings"] --> SP["SettingsPage"]
    R5["/about"] --> AB["AboutPage"]

    W --> WF["WorkspaceForm<br/>RHF + Zod + dynamic guided fields"]
    W --> SV["SolutionView<br/>formula/code/steps/warnings + copy"]
    WF --> Q["TanStack Query mutations<br/>useGenerateSolution"]
    SP --> QP["useProviders / useUpdateProvider<br/>useTestProvider / useAppSettings"]
    AN --> QF["api.analyzeFile (FormData)"]
    Q -->|"/api/v1 (Vite proxy in dev,<br/>same origin in prod)"| API2["FastAPI"]
    QP --> API2
    QF --> API2
    H --> QH["useHistory / useHistoryItem"]
    QH --> API2
```

## 6. Error & degradation model

```mermaid
flowchart TD
    E["Provider call fails"] --> T{transient?<br/>429 / 5xx / timeout / connect}
    T -- no (auth, bad request) --> F1["fail fast, normalized message<br/>+ request_id"]
    T -- yes, budget left --> RETRY["bounded retry (same provider)"]
    RETRY --> E
    T -- budget exhausted --> FB{use_fallback AND<br/>fallback configured?}
    FB -- no --> F2["generation_failed error<br/>surfaced to UI"]
    FB -- yes --> FB2["call fallback provider"]
    FB2 --> PARSE
    PARSE{"parse JSON from reply"}
    PARSE -- ok --> VAL{"schema valid?"}
    PARSE -- unparseable --> REPAIR
    VAL -- no --> REPAIR["one repair round-trip"]
    REPAIR --> VAL2{"valid now?"}
    VAL2 -- yes --> OK["clean solution"]
    VAL2 -- no --> DEG["degraded solution<br/>raw output in code field<br/>degraded_notice + badge in UI"]
    VAL -- yes --> SAFE["safety scan → warnings"]
    SAFE --> OK
```

Every terminal state is visible in the UI: clean, **Fallback used**, **Degraded**, or a
structured error with the backend's exact reason and request ID.
