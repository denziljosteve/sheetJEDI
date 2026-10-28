import { Link } from 'react-router-dom'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { APP_NAME, APP_TAGLINE, AUTHOR } from '../lib/credits'
import { PRESETS } from '../lib/constants'
import { useProviders } from '../lib/queries'

const FEATURES = [
  {
    title: 'Formulas that actually fit',
    body: 'XLOOKUP, INDEX/MATCH, SUMIFS, ARRAYFORMULA and dynamic arrays — with the exact ranges and steps for your sheet.',
  },
  {
    title: 'VBA, Office Scripts, Apps Script',
    body: 'Macros and automation for Excel desktop, Excel on the web and Google Sheets, with placement instructions.',
  },
  {
    title: 'Structured, safe output',
    body: 'Every answer arrives as title, explanation, steps, warnings and copy-ready code. Generated code is never executed for you.',
  },
  {
    title: '6 AI providers, one workflow',
    body: 'Groq, OpenRouter, OpenAI, Anthropic, OmniRoute and LongCat behind a single abstraction with explicit fallback.',
  },
  {
    title: 'Local-first & private',
    body: 'Runs on your machine. API keys are encrypted at rest with Fernet and never returned to the browser or logged.',
  },
  {
    title: 'File analysis with consent',
    body: 'Upload a workbook for instant local profiling — content is deleted immediately and only sent to a provider if you say so.',
  },
]

const STATUS_TONE: Record<string, 'success' | 'warning' | 'danger' | 'neutral'> = {
  tested: 'success',
  configured: 'warning',
  unconfigured: 'neutral',
  failed: 'danger',
}

export function HomePage() {
  const { data: providers } = useProviders()
  const configuredCount = (providers ?? []).filter((p) => p.config_status !== 'unconfigured').length

  return (
    <div className="space-y-12">
      <section className="space-y-5 pt-4 text-center" data-testid="home-hero">
        <Badge tone="accent">AI copilot for spreadsheets</Badge>
        <h1 className="mx-auto max-w-3xl text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
          Turn plain English into <span className="text-primary">formulas, macros and scripts</span>
        </h1>
        <p className="mx-auto max-w-2xl text-muted-foreground">{APP_TAGLINE}</p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link to="/generate/formula">
            <Button size="lg" data-testid="hero-open-workspace">
              Open the workspace
            </Button>
          </Link>
          <Link to="/analyzer">
            <Button variant="outline" size="lg">
              Analyse a workbook
            </Button>
          </Link>
        </div>
        <p className="text-xs text-muted-foreground">
          Local-first · no account required · your keys stay encrypted on this machine
        </p>
      </section>

      <section aria-labelledby="tasks-heading" data-testid="home-tasks">
        <h2 id="tasks-heading" className="mb-4 text-center text-2xl font-semibold">
          What do you want to build today?
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {PRESETS.map((preset) => (
            <Link
              key={preset.slug}
              to={`/generate/${preset.slug}`}
              className="group rounded-lg border border-border bg-card p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary focus-visible:outline-2 focus-visible:outline-primary"
              data-testid={`preset-${preset.slug}`}
            >
              <h3 className="font-semibold group-hover:text-primary">{preset.label}</h3>
              <p className="mt-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {preset.short}
              </p>
              <p className="mt-2 text-sm text-muted-foreground">{preset.description}</p>
            </Link>
          ))}
        </div>
      </section>

      <section aria-labelledby="features-heading" className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <h2 id="features-heading" className="sr-only">
          Features
        </h2>
        {FEATURES.map((f) => (
          <Card key={f.title}>
            <CardHeader title={f.title} />
            <CardBody className="pt-1">
              <p className="text-sm text-muted-foreground">{f.body}</p>
            </CardBody>
          </Card>
        ))}
      </section>

      <section aria-labelledby="providers-heading" className="rounded-lg border border-border bg-card p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 id="providers-heading" className="text-lg font-semibold">
            Provider status
          </h2>
          <Link to="/settings" className="text-sm text-primary underline-offset-2 hover:underline">
            Configure in Settings →
          </Link>
        </div>
        <p className="mb-3 text-sm text-muted-foreground">
          {providers
            ? `${configuredCount} of ${providers.length} providers configured on this machine.`
            : 'Checking provider status…'}
        </p>
        <div className="flex flex-wrap gap-2">
          {(providers ?? []).map((p) => (
            <span
              key={p.name}
              className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1 text-xs"
              title={p.status_note ?? p.verification_status}
            >
              <span className="font-medium">{p.display_name}</span>
              <Badge tone={STATUS_TONE[p.config_status] ?? 'neutral'}>{p.config_status}</Badge>
            </span>
          ))}
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          Protocol verification status per adapter:{' '}
          {(providers ?? [])
            .map((p) => `${p.display_name}: ${p.verification_status}`)
            .join(' · ') || '—'}
        </p>
      </section>

      <section className="rounded-lg border border-border bg-muted p-5 text-sm text-muted-foreground">
        <p>
          Built by <span className="font-medium text-foreground">{AUTHOR.name}</span> ·{' '}
          <a className="text-primary underline-offset-2 hover:underline" href={`mailto:${AUTHOR.email}`}>
            {AUTHOR.email}
          </a>{' '}
          · {APP_NAME} keeps your data on this machine — only the prompts you send (and only with
          your consent for file context) reach an AI provider.
        </p>
      </section>
    </div>
  )
}
