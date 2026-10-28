export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-md bg-muted ${className ?? 'h-4 w-full'}`}
    />
  )
}

export function SkeletonSolution() {
  return (
    <div aria-label="Loading solution" className="space-y-4" role="status">
      <Skeleton className="h-7 w-2/3" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-5/6" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-4 w-1/2" />
      <span className="sr-only">Generating solution…</span>
    </div>
  )
}
