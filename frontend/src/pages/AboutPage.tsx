import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { APP_NAME, APP_TAGLINE, AUTHOR } from '../lib/credits'
import { useProviders } from '../lib/queries'

const STACK = [
  { area: 'Frontend', items: 'React 19, TypeScript, Vite, Tailwind CSS v4, React Hook Form + Zod, TanStack Query, React Router, Monaco Editor' },
  { area: 'Backend', items: 'FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Python 3.12' },
  { area: 'Storage', items: 'SQLite by default (Postgres via env var) — runs entirely on your machine' },
  { area: 'Providers', items: 'Groq, OpenRouter, OpenAI, Anthropic, OmniRoute, LongCat behind one abstraction' },
  { area: 'Quality', items: 'pytest (backend), Vitest + React Testing Library (frontend), ruff, mypy, oxlint, tsc strict' },
]

const PRINCIPLES = [
  'Your API keys are encrypted at rest with Fernet and are never returned to the browser or written to logs — only masked hints like ••••7890.',
  'Nothing is executed for you: sheetJEDI generates formulas and code, you review and run them.',
  'Destructive operations (deleting ranges, overwriting workbooks, sending data) are always flagged in the warnings section.',
  'File uploads are validated, analysed locally and deleted immediately; workbook context is only sent to a provider with your explicit per-request consent.',
  'Retries apply only to transient failures (429/5xx/timeouts) and are bounded; failures are surfaced with the exact reason.',
  'When a fallback provider answers, the result is labelled “Fallback used”. When validation degrades, you are told too.',
]

export function AboutPage() {
  const { data: providers } = useProviders()

  return (
    <div className="space-y-6" data-testid="about-page">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">About {APP_NAME}</h1>
        <p className="text-sm text-muted-foreground">{APP_TAGLINE}</p>
      </header>

      <Card>
        <CardHeader title="Author" />
        <CardBody className="space-y-1 pt-1 text-sm">
          <p>
            <span className="font-semibold">{AUTHOR.name}</span> — creator, architect and
            implementer of sheetJEDI.
          </p>
          <p>
            Email:{' '}
            <a className="text-primary underline-offset-2 hover:underline" href={`mailto:${AUTHOR.email}`}>
              {AUTHOR.email}
            </a>
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            <a className="text-primary underline-offset-2 hover:underline" href={AUTHOR.linkedin} target="_blank" rel="noreferrer">
              LinkedIn
            </a>
            <a className="text-primary underline-offset-2 hover:underline" href={AUTHOR.portfolio} target="_blank" rel="noreferrer">
              Portfolio
            </a>
            <a className="text-primary underline-offset-2 hover:underline" href={AUTHOR.github} target="_blank" rel="noreferrer">
              GitHub
            </a>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="What it does"
          description="Ask in plain language; get a structured solution back."
        />
        <CardBody className="space-y-2 pt-1 text-sm text-muted-foreground">
          <p>
            {APP_NAME} turns requests like “look up the price by SKU and flag anything below cost”
            into ready-to-use Excel / Google Sheets formulas, VBA macros, Office Scripts and Google
            Apps Script — plus data-cleaning, analysis, reporting and troubleshooting guidance.
          </p>
          <p>
            Every answer is parsed into a strict schema (title, explanation, steps, formula, code,
            warnings, alternatives, common errors). If the model output cannot be validated, one
            automatic repair round-trip runs; if it still fails, a clearly-labelled degraded result
            is shown instead of failing silently.
          </p>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Privacy & safety principles" />
        <CardBody className="list-inside list-disc space-y-1.5 pt-1 text-sm text-muted-foreground">
          {PRINCIPLES.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Tech stack" />
        <CardBody className="space-y-2 pt-1 text-sm">
          {STACK.map((row) => (
            <div key={row.area} className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
              <span className="w-24 shrink-0 font-medium">{row.area}</span>
              <span className="text-muted-foreground">{row.items}</span>
            </div>
          ))}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Provider verification status"
          description="Honest status of each adapter as shipped in this build."
        />
        <CardBody className="space-y-2 pt-1 text-sm">
          {(providers ?? []).map((p) => (
            <div key={p.name} className="rounded-md border border-border px-3 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{p.display_name}</span>
                <Badge tone="neutral">{p.verification_status}</Badge>
                <Badge
                  tone={
                    p.config_status === 'tested'
                      ? 'success'
                      : p.config_status === 'configured'
                        ? 'warning'
                        : p.config_status === 'failed'
                          ? 'danger'
                          : 'neutral'
                  }
                >
                  {p.config_status}
                </Badge>
              </div>
              {p.status_note && (
                <p className="mt-1 text-xs text-muted-foreground">{p.status_note}</p>
              )}
            </div>
          ))}
          <p className="text-xs text-muted-foreground">
            “tested” in the second badge reflects the last live connection test run{' '}
            <span className="font-medium">from your machine</span> in Settings. Endpoints were
            protocol-verified during development; live calls require your own API keys (the
            opt-in test suite runs only when SHEETJEDI_LIVE_TESTS=1 with credentials present).
          </p>
        </CardBody>
      </Card>
    </div>
  )
}
