"""Minimal in-memory sliding-window rate limiter (per client IP).

Adequate for a local-first, single-process deployment. A production multi-node
deployment should replace this with a shared limiter (e.g. Redis) — see
PRODUCTIONDEPLOY.md.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import error_body


class SlidingWindowLimiter:
    def __init__(self, window_seconds: int = 60, max_requests: int = 30) -> None:
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            cutoff = now - self.window_seconds
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.max_requests:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def install_rate_limit(
    app: FastAPI,
    enabled: bool,
    max_requests: int,
    paths: tuple[str, ...] = ("/api/v1/solutions", "/api/v1/files"),
) -> None:
    if not enabled:
        return
    limiter = SlidingWindowLimiter(max_requests=max_requests)

    @app.middleware("http")
    async def _rate_limit(request: Request, call_next):
        if any(request.url.path.startswith(p) for p in paths):
            client = request.client.host if request.client else "unknown"
            if not limiter.allow(client):
                return JSONResponse(
                    status_code=429,
                    content=error_body(
                        "rate_limited",
                        "Too many requests. Please wait a moment and try again.",
                        getattr(request.state, "request_id", None),
                    ),
                )
        return await call_next(request)

    app.state.rate_limiter = limiter
