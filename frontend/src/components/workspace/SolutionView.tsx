import type { GenerationResponse, SolutionResponse } from '../../lib/types'
import { cn } from '../../lib/utils'
import { CopyButton } from '../CopyButton'
import { Badge } from '../ui/Badge'
import { Card, CardBody, CardHeader } from '../ui/Card'
import { CodeBlock } from './CodeBlock'

function Section({
  title,
  children,
  testId,
}: {
  title: string
  children: React.ReactNode
  testId?: string
}) {
  return (
    <section data-testid={testId} className="border-t border-border px-5 py-4">
      <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h4>
      {children}
    </section>
  )
}

export function SolutionView({
  solution,
  meta,
  compact = false,
}: {
  solution: SolutionResponse
  meta?: GenerationResponse
  compact?: boolean
}) {
  const degraded = meta?.degraded ?? false
  const fallbackUsed = meta?.fallback_used ?? false
  const hasCode = !!solution.code && solution.code.trim().length > 0
  const hasFormula = !!solution.formula && solution.formula.trim().length > 0

  return (
    <article
      className="space-y-4"
      data-testid="solution-view"
      aria-label={`Solution: ${solution.title}`}
    >
      {(degraded || fallbackUsed || (meta && meta.degraded_notice)) && (
        <div
          role="status"
          data-testid="solution-notice"
          className={cn(
            'rounded-lg border px-4 py-3 text-sm',
            degraded
              ? 'border-warning/50 bg-warning/10 text-foreground'
              : 'border-accent/50 bg-accent/10 text-foreground',
          )}
        >
          <p className="font-semibold">Transparency notice</p>
          <ul className="mt-1 list-inside list-disc space-y-0.5 text-muted-foreground">
            {degraded && (
              <li>
                Structured validation could not be completed — the raw model output is shown as-is
                ({solution.code_language ?? 'unvalidated_output'}).
              </li>
            )}
            {meta?.degraded_notice && <li>{meta.degraded_notice}</li>}
            {fallbackUsed && (
              <li>
                The primary provider was unavailable (rate limit, outage or config issue); a
                fallback provider answered this request.
              </li>
            )}
          </ul>
        </div>
      )}

      <Card>
        <CardHeader
          title={<span data-testid="solution-title">{solution.title}</span>}
          description={solution.summary}
          actions={
            <div className="flex flex-wrap items-center gap-1.5">
              {meta && (
                <>
                  <Badge tone="info">{meta.provider}</Badge>
                  <Badge tone="neutral">{meta.model}</Badge>
                </>
              )}
              <Badge tone="neutral">{solution.platform === 'excel' ? 'Excel' : 'Google Sheets'}</Badge>
              {fallbackUsed && <Badge tone="warning">Fallback used</Badge>}
              {degraded && <Badge tone="warning">Degraded</Badge>}
            </div>
          }
        />
        <CardBody className="pt-1">
          <p className="text-sm leading-relaxed text-muted-foreground">{solution.explanation}</p>
        </CardBody>

        {hasFormula && (
          <Section title="Formula" testId="solution-formula">
            <div className="rounded-md border border-border bg-muted p-4">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Paste into your cell
                </span>
                <CopyButton text={solution.formula as string} label="Copy formula" />
              </div>
              <pre className="overflow-x-auto whitespace-pre-wrap break-all font-mono text-sm leading-relaxed">
                <code>{solution.formula}</code>
              </pre>
            </div>
          </Section>
        )}

        {hasCode && (
          <Section title="Code" testId="solution-code">
            <CodeBlock
              code={solution.code as string}
              language={solution.code_language ?? 'plaintext'}
              label={solution.code_language ?? 'code'}
            />
            <p className="mt-2 text-xs text-muted-foreground">
              sheetJEDI never executes generated code — review it and run it yourself.
            </p>
          </Section>
        )}

        {solution.prerequisites.length > 0 && (
          <Section title="Prerequisites" testId="solution-prerequisites">
            <ul className="list-inside list-disc space-y-1 text-sm">
              {solution.prerequisites.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </Section>
        )}

        {solution.assumptions.length > 0 && (
          <Section title="Assumptions" testId="solution-assumptions">
            <ul className="list-inside list-disc space-y-1 text-sm">
              {solution.assumptions.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </Section>
        )}

        {solution.implementation_steps.length > 0 && (
          <Section title="Implementation steps" testId="solution-steps">
            <ol className="space-y-3">
              {solution.implementation_steps.map((step, i) => (
                <li key={i} className="flex gap-3 text-sm">
                  <span
                    aria-hidden="true"
                    className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground"
                  >
                    {i + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="font-medium">{step.title}</p>
                    <p className="mt-0.5 whitespace-pre-wrap text-muted-foreground">
                      {step.instructions}
                    </p>
                    {step.cell_references.length > 0 && (
                      <p className="mt-1 font-mono text-xs text-accent">
                        {step.cell_references.join(', ')}
                      </p>
                    )}
                    {step.code_location && (
                      <p className="mt-1 text-xs text-muted-foreground">{step.code_location}</p>
                    )}
                  </div>
                </li>
              ))}
            </ol>
            <div className="mt-3">
              <CopyButton
                text={solution.implementation_steps
                  .map((s, i) => `${i + 1}. ${s.title}\n${s.instructions}`)
                  .join('\n\n')}
                label="Copy steps"
              />
            </div>
          </Section>
        )}

        {(solution.example_input || solution.expected_output) && (
          <Section title="Example" testId="solution-example">
            {solution.example_input && (
              <div className="mb-2">
                <p className="mb-1 text-xs font-medium text-muted-foreground">Input</p>
                <pre className="overflow-x-auto rounded-md border border-border bg-muted p-3 font-mono text-xs">
                  {solution.example_input}
                </pre>
              </div>
            )}
            {solution.expected_output && (
              <div>
                <p className="mb-1 text-xs font-medium text-muted-foreground">Expected output</p>
                <pre className="overflow-x-auto rounded-md border border-border bg-muted p-3 font-mono text-xs">
                  {solution.expected_output}
                </pre>
              </div>
            )}
          </Section>
        )}

        {solution.alternative_solutions.length > 0 && (
          <Section title="Alternative approaches" testId="solution-alternatives">
            <div className="space-y-3">
              {solution.alternative_solutions.map((alt, i) => (
                <div key={i} className="rounded-md border border-border p-3">
                  <p className="text-sm font-medium">{alt.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{alt.description}</p>
                  {alt.formula && (
                    <pre className="mt-2 overflow-x-auto rounded bg-muted p-2 font-mono text-xs">
                      {alt.formula}
                    </pre>
                  )}
                  {alt.when_to_use && (
                    <p className="mt-2 text-xs italic text-muted-foreground">
                      When to use: {alt.when_to_use}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </Section>
        )}

        {solution.warnings.length > 0 && (
          <Section title="Warnings" testId="solution-warnings">
            <ul
              className="space-y-2 rounded-md border border-warning/50 bg-warning/10 p-3 text-sm"
              data-testid="solution-warnings-list"
            >
              {solution.warnings.map((w, i) => (
                <li key={i} className="flex gap-2">
                  <span aria-hidden="true">⚠️</span>
                  <span>{w}</span>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {solution.common_errors.length > 0 && (
          <Section title="Common errors" testId="solution-errors">
            <div className="space-y-3">
              {solution.common_errors.map((err, i) => (
                <div key={i} className="rounded-md border border-border p-3 text-sm">
                  <p className="font-mono font-medium text-danger">{err.error}</p>
                  <p className="mt-1 text-muted-foreground">
                    <span className="font-medium text-foreground">Cause:</span> {err.cause}
                  </p>
                  <p className="mt-1 text-muted-foreground">
                    <span className="font-medium text-foreground">Fix:</span> {err.solution}
                  </p>
                </div>
              ))}
            </div>
          </Section>
        )}

        {solution.troubleshooting.length > 0 && (
          <Section title="Troubleshooting checklist" testId="solution-troubleshooting">
            <ul className="list-inside list-disc space-y-1 text-sm">
              {solution.troubleshooting.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </Section>
        )}

        {solution.confidence_notes && (
          <Section title="Confidence notes" testId="solution-confidence">
            <p className="text-sm text-muted-foreground">{solution.confidence_notes}</p>
          </Section>
        )}

        {!compact && (
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-5 py-3 text-xs text-muted-foreground">
            <span>
              {meta?.solution_id
                ? `Saved to history (id ${meta.solution_id.slice(0, 8)}…)`
                : 'Not saved to history'}
            </span>
            {meta && <span>Generated {new Date(meta.generated_at).toLocaleString()}</span>}
          </div>
        )}
      </Card>
    </article>
  )
}
