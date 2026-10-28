import { useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { SolutionView } from '../components/workspace/SolutionView'
import { WorkspaceForm } from '../components/workspace/WorkspaceForm'
import { Card, CardBody } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Skeleton'
import { ApiError } from '../lib/api'
import { presetBySlug } from '../lib/constants'
import { useGenerateSolution } from '../lib/queries'

function friendlyError(err: unknown): string {
  if (err instanceof ApiError) {
    const hints: Record<string, string> = {
      rate_limited: 'Too many requests — wait a moment and try again.',
      provider_not_configured:
        'No provider is configured. Add an API key in Settings (it is stored encrypted).',
      no_provider_configured:
        'No provider is configured. Add an API key in Settings (it is stored encrypted).',
      provider_auth_failed: 'The provider rejected the API key — check it in Settings.',
      upstream_error: 'The AI provider returned an error — try again or switch provider.',
      upstream_timeout: 'The AI provider timed out — try again or pick a faster model.',
      generation_failed: 'Generation failed after retries — try rephrasing or another provider.',
      validation_error: 'The request was rejected — check the fields and try again.',
    }
    const hint = hints[err.code]
    const rid = err.requestId ? ` (request ${err.requestId})` : ''
    return hint ? `${err.message} ${hint}${rid}` : `${err.message}${rid}`
  }
  return err instanceof Error ? err.message : 'Something went wrong. Please try again.'
}

export function WorkspacePage() {
  const { preset: presetSlug } = useParams<{ preset?: string }>()
  const preset = presetBySlug(presetSlug)
  const generate = useGenerateSolution()
  const result = generate.data ?? null
  const resultRef = useRef<HTMLDivElement>(null)
  const knownSlug = presetSlug === undefined || preset !== null

  useEffect(() => {
    if (result) {
      resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [result])

  return (
    <div className="space-y-8" data-testid="workspace-page">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">{preset ? preset.label : 'Workspace'}</h1>
        <p className="text-sm text-muted-foreground">
          {preset
            ? preset.description
            : 'Describe any spreadsheet task — formulas, macros, scripts, cleaning, analysis and more.'}
        </p>
        {!knownSlug && (
          <p role="status" className="text-sm text-warning">
            Unknown preset “{presetSlug}” — showing the general workspace instead.
          </p>
        )}
      </header>

      <WorkspaceForm
        preset={preset}
        loading={generate.isPending}
        error={generate.isError ? friendlyError(generate.error) : null}
        onSubmitRequest={(body) => generate.mutate(body)}
      />

      {generate.isPending && (
        <Card data-testid="loading-solution">
          <CardBody className="space-y-3">
            <p className="text-sm font-medium">Generating your solution…</p>
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-32 w-full" />
            <p className="text-xs text-muted-foreground">
              Structured validation, one repair round-trip and provider fallback (if enabled) run
              server-side.
            </p>
          </CardBody>
        </Card>
      )}

      {result && !generate.isPending && (
        <div ref={resultRef} className="scroll-mt-20 space-y-3">
          <h2 className="text-lg font-semibold">Solution</h2>
          <SolutionView solution={result.solution} meta={result} />
        </div>
      )}
    </div>
  )
}
