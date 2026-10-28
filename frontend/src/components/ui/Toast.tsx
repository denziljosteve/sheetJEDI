import { useCallback, useMemo, useRef, useState, type ReactNode } from "react";
import { ToastContext, type ToastItem, type ToastTone } from "./toast-context";

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const remove = useCallback((id: number) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  const push = useCallback(
    (message: string, tone: ToastTone = "info") => {
      const id = nextId.current++;
      setItems((current) => [...current, { id, message, tone }]);
      window.setTimeout(() => remove(id), 4500);
    },
    [remove],
  );

  const value = useMemo(() => ({ push }), [push]);

  const toneClasses: Record<ToastTone, string> = {
    success: "border-success/40 bg-success/10 text-foreground",
    error: "border-danger/40 bg-danger/10 text-foreground",
    info: "border-border bg-card text-foreground",
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-center gap-2 sm:inset-x-auto sm:right-6 sm:items-end"
      >
        {items.map((item) => (
          <div
            key={item.id}
            role="status"
            data-testid="toast"
            className={`pointer-events-auto w-full max-w-sm rounded-lg border px-4 py-3 text-sm shadow-lg backdrop-blur ${toneClasses[item.tone]}`}
          >
            <div className="flex items-start justify-between gap-3">
              <span>{item.message}</span>
              <button
                type="button"
                onClick={() => remove(item.id)}
                className="rounded p-1 text-muted transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-primary"
                aria-label="Dismiss notification"
              >
                ✕
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
