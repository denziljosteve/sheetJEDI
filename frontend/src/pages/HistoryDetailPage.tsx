import { Link, useParams } from 'react-router-dom'
import { SolutionView } from '../components/workspace/SolutionView'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Skeleton'
import { ApiError } from '../lib/api'
import { TASK_TYPE_LABELS } from '../lib/constants'
import { useHistoryItem } from '../lib/queries'
import { formatDate } from '../lib/utils'
import type { GenerationResponse, TaskType } from '../lib/types'

export function HistoryDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: detail, isPending, isError, error, refetch } = useHistoryItem(id ?? null)

  if (isPending) {
    return (
      <div className="space-y-4" data-testid="history-detail-loading">
        <Skeleton className="h-6 w-1/2" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (isError) {
    const message =
      error instanceof ApiError
        ? error.message
        : error instanceof Error
          ? error.message
          : 'Failed to load entry'
    return (
      <div className="space-y-4">
        <div role="alert" className="rounded-md border border-danger/50 bg-danger/10 px-4 py-3 text-sm">
          {message}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => void refetch()}>
            Retry
          </Button>
          <Link to="/history">
            <Button variant="ghost" size="sm">
              Back to history
            </Button>
          </Link>
        </div>
      </div>
    )
  }

  const meta: GenerationResponse = {
    solution: detail.solution,
    solution_id: detail.id,
    provider: detail.provider ?? 'unknown',
    model: detail.model ?? 'unknown',
    fallback_used: detail.fallback_used,
    degraded: false,
    degraded_notice: null,
    usage: null,
    generated_at: detail.created_at,
  }

  const taskLabel =
    TASK_TYPE_LABELS[detail.task_type as TaskType] ?? detail.task_type

  return (
    <div className="space-y-6" data-testid="history-detail-page">
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Link to="/history">
            <Button variant="ghost" size="sm">
              ← Back to history
            </Button>
          </Link>
          <Badge tone="neutral">
            {detail.platform === 'excel' ? 'Excel' : 'Google Sheets'}
          </Badge>
          <Badge tone="info">{taskLabel}</Badge>
          {detail.fallback_used && <Badge tone="warning">Fallback used</Badge>}
          <span className="text-xs text-muted-foreground">{formatDate(detail.created_at)}</span>
        </div>
      </header>

      <details className="rounded-lg border border-border bg-card">
        <summary className="cursor-pointer px-5 py-3 text-sm font-semibold">
          Original request &amp; context
        </summary>
        <div className="border-t border-border px-5 py-4">
          <pre className="overflow-x-auto whitespace-pre-wrap rounded-md bg-muted p-3 font-mono text-xs">
            {JSON.stringify(detail.request, null, 2)}
          </pre>
        </div>
      </details>

      <SolutionView solution={detail.solution} meta={meta} />

      <Card>
        <CardHeader title="What now?" />
        <CardBody className="flex flex-wrap gap-2 pt-1">
          <Link to="/generate/formula">
            <Button variant="outline" size="sm">
              New request
            </Button>
          </Link>
          <Link to="/settings">
            <Button variant="ghost" size="sm">
              Provider settings
            </Button>
          </Link>
        </CardBody>
      </Card>
    </div>
  )
}
