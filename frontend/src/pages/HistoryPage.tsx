import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { Dialog } from '../components/ui/Dialog'
import { Skeleton } from '../components/ui/Skeleton'
import { useDeleteHistoryItem, useHistory } from '../lib/queries'
import { formatDate } from '../lib/utils'
import type { HistoryItem } from '../lib/types'

const PAGE_SIZE = 20

export function HistoryPage() {
  const [offset, setOffset] = useState(0)
  const { data, isPending, isError, error, refetch } = useHistory(PAGE_SIZE, offset)
  const [pendingDelete, setPendingDelete] = useState<HistoryItem | null>(null)
  const remove = useDeleteHistoryItem()

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1
  const page = Math.floor(offset / PAGE_SIZE) + 1

  return (
    <div className="space-y-6" data-testid="history-page">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">History</h1>
        <p className="text-sm text-muted-foreground">
          Locally stored past generations. Delete any entry at any time — nothing leaves this
          machine.
        </p>
      </header>

      <Card>
        <CardHeader
          title={`Saved solutions${data ? ` (${data.total})` : ''}`}
          actions={
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                Previous
              </Button>
              <span className="text-xs text-muted-foreground">
                Page {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={!data || offset + PAGE_SIZE >= data.total}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          }
        />
        <CardBody className="pt-2">
          {isPending && (
            <div className="space-y-3" data-testid="history-loading">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          )}

          {isError && (
            <div role="alert" className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-danger/50 bg-danger/10 px-3 py-2 text-sm">
              <span>
                Could not load history: {error instanceof Error ? error.message : 'unknown error'}
              </span>
              <Button size="sm" variant="outline" onClick={() => void refetch()}>
                Retry
              </Button>
            </div>
          )}

          {data && data.items.length === 0 && (
            <div className="py-8 text-center text-sm text-muted-foreground" data-testid="history-empty">
              <p>No saved solutions yet.</p>
              <Link to="/generate/formula" className="mt-2 inline-block text-primary underline-offset-2 hover:underline">
                Generate your first one →
              </Link>
            </div>
          )}

          {data && data.items.length > 0 && (
            <ul className="divide-y divide-border" data-testid="history-list">
              {data.items.map((item) => (
                <li key={item.id} className="flex flex-wrap items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <Link
                      to={`/history/${item.id}`}
                      className="block truncate text-sm font-medium hover:text-primary focus-visible:outline-2 focus-visible:outline-primary"
                    >
                      {item.title || item.request_preview || '(untitled request)'}
                    </Link>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      {item.request_preview}
                    </p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs">
                      <Badge tone="neutral">
                        {item.platform === 'excel' ? 'Excel' : 'Google Sheets'}
                      </Badge>
                      <Badge tone="info">{item.task_type}</Badge>
                      {item.fallback_used && <Badge tone="warning">Fallback used</Badge>}
                      {item.provider && <Badge tone="neutral">{item.provider}</Badge>}
                      <span className="text-muted-foreground">{formatDate(item.created_at)}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Link to={`/history/${item.id}`}>
                      <Button variant="outline" size="sm">
                        Open
                      </Button>
                    </Link>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setPendingDelete(item)}
                      aria-label={`Delete ${item.title || 'entry'}`}
                    >
                      Delete
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      <Dialog
        open={pendingDelete !== null}
        onClose={() => setPendingDelete(null)}
        title="Delete this entry?"
        footer={
          <>
            <Button variant="outline" size="sm" onClick={() => setPendingDelete(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              loading={remove.isPending}
              onClick={() => {
                if (!pendingDelete) return
                remove.mutate(pendingDelete.id, {
                  onSettled: () => setPendingDelete(null),
                })
              }}
            >
              Delete
            </Button>
          </>
        }
      >
        <p>
          The saved solution “{pendingDelete?.title || pendingDelete?.request_preview || 'entry'}”
          will be permanently removed from local history.
        </p>
        {remove.isError && (
          <p role="alert" className="mt-2 text-sm text-danger">
            Delete failed: {remove.error instanceof Error ? remove.error.message : 'unknown error'}
          </p>
        )}
      </Dialog>
    </div>
  )
}
