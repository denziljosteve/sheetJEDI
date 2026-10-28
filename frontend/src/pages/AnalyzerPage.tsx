import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { Label, Input } from '../components/ui/Field'
import { ApiError, api } from '../lib/api'
import { clearAttachment, writeAttachment } from '../lib/attachment'
import { formatBytes, formatDate } from '../lib/utils'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { WorkbookAnalysis } from '../lib/types'

const ACCEPT = '.xlsx,.xlsm,.csv,.txt'

export function AnalyzerPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const [consent, setConsent] = useState(false)
  const [analysis, setAnalysis] = useState<WorkbookAnalysis | null>(null)

  const analyze = useMutation({
    mutationFn: ({ file, consent }: { file: File; consent: boolean }) =>
      api.analyzeFile(file, consent),
    onSuccess: (data) => {
      setAnalysis(data)
      writeAttachment({ file_id: data.file_id, filename: data.filename })
    },
    onError: () => {
      setAnalysis(null)
    },
  })

  const removeAnalysis = useMutation({
    mutationFn: (fileId: string) => api.deleteFile(fileId),
    onSuccess: () => {
      setAnalysis(null)
      clearAttachment()
      void qc.invalidateQueries({ queryKey: ['history'] })
    },
  })

  const errorMessage = (): string | null => {
    if (!analyze.isError) return null
    const err = analyze.error
    if (err instanceof ApiError) {
      const rid = err.requestId ? ` (request ${err.requestId})` : ''
      return `${err.message}${rid}`
    }
    return err instanceof Error ? err.message : 'Upload failed.'
  }

  return (
    <div className="space-y-6" data-testid="analyzer-page">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">File Analyzer</h1>
        <p className="text-sm text-muted-foreground">
          Profile a workbook locally: sheet names, headers, column types, samples and cleaning
          recommendations. Supported: .xlsx, .xlsm, .csv, .txt.
        </p>
      </header>

      <Card>
        <CardHeader
          title="Upload a workbook"
          description="Your file is written to a private temp location, analysed, and deleted immediately — only the structured profile is kept."
        />
        <CardBody className="space-y-4">
          <div>
            <Label htmlFor="analyzer-file" required>
              File
            </Label>
            <Input
              id="analyzer-file"
              type="file"
              accept={ACCEPT}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              data-testid="analyzer-file-input"
            />
          </div>

          <label className="flex items-start gap-2 text-sm" data-testid="analyzer-consent">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 accent-[var(--primary)]"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
            />
            <span>
              I consent to <span className="font-medium">local analysis</span> of this file on my
              machine. (Sending workbook context to an AI provider requires a separate, per-request
              consent in the workspace.)
            </span>
          </label>

          {analyze.isError && (
            <div role="alert" data-testid="analyzer-error" className="rounded-md border border-danger/50 bg-danger/10 px-3 py-2 text-sm">
              {errorMessage()}
            </div>
          )}

          <div className="flex justify-end">
            <Button
              disabled={!file || !consent}
              loading={analyze.isPending}
              onClick={() => file && analyze.mutate({ file, consent })}
              data-testid="analyzer-analyze"
            >
              {analyze.isPending ? 'Analysing…' : 'Analyse locally'}
            </Button>
          </div>
        </CardBody>
      </Card>

      {analysis && (
        <div className="space-y-4" data-testid="analysis-result">
          <Card>
            <CardHeader
              title={
                <span className="flex flex-wrap items-center gap-2">
                  {analysis.filename}
                  <Badge tone="neutral">{analysis.file_type}</Badge>
                  <Badge tone="info">{analysis.sheet_count} sheet(s)</Badge>
                  <Badge tone="neutral">{formatBytes(analysis.size_bytes)}</Badge>
                </span>
              }
              description={`Analysed ${formatDate(analysis.analyzed_at)} · id ${analysis.file_id.slice(0, 8)}…`}
              actions={
                <>
                  <Link to="/generate/formula">
                    <Button size="sm" data-testid="analyzer-use-workspace">
                      Use in workspace
                    </Button>
                  </Link>
                  <Button
                    size="sm"
                    variant="danger"
                    loading={removeAnalysis.isPending}
                    onClick={() => removeAnalysis.mutate(analysis.file_id)}
                  >
                    Delete analysis
                  </Button>
                </>
              }
            />
            <CardBody className="space-y-5">
              {analysis.recommendations.length > 0 && (
                <div>
                  <h3 className="mb-2 text-sm font-semibold">Recommendations</h3>
                  <ul className="space-y-1.5 text-sm">
                    {analysis.recommendations.map((r, i) => (
                      <li key={i} className="rounded-md border border-accent/40 bg-accent/5 p-2">
                        <span className="font-medium">{r.area}:</span> {r.recommendation}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {analysis.notes.length > 0 && (
                <div>
                  <h3 className="mb-2 text-sm font-semibold">Notes</h3>
                  <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
                    {analysis.notes.map((n, i) => (
                      <li key={i}>{n}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="space-y-6">
                {analysis.sheets.map((sheet) => (
                  <section key={sheet.name} className="rounded-md border border-border p-4">
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                      <h3 className="font-semibold">{sheet.name}</h3>
                      <div className="flex flex-wrap gap-1.5">
                        <Badge tone="neutral">{sheet.total_columns} columns</Badge>
                        <Badge tone="neutral">
                          {sheet.total_rows_estimate ?? sheet.scanned_rows} rows
                          {sheet.truncated ? ' (sampled)' : ''}
                        </Badge>
                        {sheet.duplicate_rows_scanned > 0 && (
                          <Badge tone="warning">
                            {sheet.duplicate_rows_scanned} duplicate rows found
                          </Badge>
                        )}
                      </div>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-border text-muted-foreground">
                            <th scope="col" className="py-1.5 pr-3 font-medium">
                              Column
                            </th>
                            <th scope="col" className="py-1.5 pr-3 font-medium">
                              Type
                            </th>
                            <th scope="col" className="py-1.5 pr-3 font-medium">
                              Non-empty
                            </th>
                            <th scope="col" className="py-1.5 pr-3 font-medium">
                              Distinct
                            </th>
                            <th scope="col" className="py-1.5 font-medium">
                              Samples
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {sheet.columns.map((col, i) => (
                            <tr key={`${col.name}-${i}`} className="border-b border-border/50">
                              <td className="py-1.5 pr-3 font-mono">{col.name}</td>
                              <td className="py-1.5 pr-3">
                                <Badge tone={col.inferred_type === 'mixed' ? 'warning' : 'info'}>
                                  {col.inferred_type}
                                </Badge>
                              </td>
                              <td className="py-1.5 pr-3">{col.non_empty}</td>
                              <td className="py-1.5 pr-3">{col.distinct_sampled}</td>
                              <td className="max-w-64 truncate py-1.5 text-muted-foreground">
                                {col.sample_values.join(', ')}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {sheet.sample_rows.length > 0 && (
                      <details className="mt-3">
                        <summary className="cursor-pointer text-xs font-medium text-primary">
                          Preview first {sheet.sample_rows.length} rows
                        </summary>
                        <div className="mt-2 overflow-x-auto">
                          <table className="w-full text-left text-xs">
                            <thead>
                              <tr className="border-b border-border">
                                {sheet.headers.map((h, i) => (
                                  <th key={i} scope="col" className="py-1.5 pr-3 font-medium">
                                    {h}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {sheet.sample_rows.map((row, ri) => (
                                <tr key={ri} className="border-b border-border/50">
                                  {row.map((cell, ci) => (
                                    <td key={ci} className="max-w-40 truncate py-1.5 pr-3">
                                      {cell ?? ''}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </details>
                    )}
                  </section>
                ))}
              </div>
            </CardBody>
          </Card>

          <p className="text-xs text-muted-foreground">
            The uploaded file content has been deleted from disk. The stored analysis can be
            attached to a workspace request — the extracted context is only sent to an AI provider
            when you explicitly consent per request.{' '}
            <button
              type="button"
              className="text-primary underline-offset-2 hover:underline"
              onClick={() => navigate('/settings')}
            >
              Review privacy settings
            </button>
          </p>
        </div>
      )}
    </div>
  )
}
