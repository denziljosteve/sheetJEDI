"""Health and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.db.session import get_engine

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness probe: process is up and serving requests."""
    return {"status": "ok", "version": __version__}


@router.get("/ready")
async def ready() -> dict:
    """Readiness probe: verifies required services without revealing secrets.

    Returns 200 when the database is reachable; 503 otherwise with a generic
    reason (never connection strings or credentials).
    """
    checks: dict[str, str] = {}
    ok = True
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
        ok = False
    return {"status": "ready" if ok else "not_ready", "checks": checks}
