"""FastAPI application entrypoint.

Run from the ``backend/`` directory:

    python -m uvicorn app.main:app --reload

In production, run ``alembic upgrade head`` before starting (init_db() skips
automatic table creation when SHEETJEDI_ENV=production).
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app import __version__
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.ratelimit import install_rate_limit
from app.db.session import get_session_factory, init_db
from app.services.files import purge_expired_files

logger = logging.getLogger(__name__)

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    init_db(settings)
    # Opportunistically clear expired file-analysis records at startup.
    try:
        session = get_session_factory(settings)()
        try:
            purge_expired_files(session)
        finally:
            session.close()
    except Exception:  # pragma: no cover - startup best effort
        logger.warning("Startup file purge failed", exc_info=True)
    logger.info("sheetJEDI backend started (env=%s, version=%s)", settings.env, __version__)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="sheetJEDI API",
        description=(
            "AI copilot for Excel and Google Sheets — natural language in, "
            "formulas, code, and step-by-step guidance out."
        ),
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )

    install_rate_limit(
        app,
        enabled=settings.rate_limit_enabled,
        max_requests=settings.rate_limit_requests_per_minute,
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/api/v1", include_in_schema=False)
    async def api_root() -> JSONResponse:
        return JSONResponse({"name": "sheetJEDI API", "version": __version__})

    # Serve the built frontend (when present) with SPA fallback.
    if FRONTEND_DIST.exists():
        app.mount(
            "/assets",
            name="frontend-assets",
            app=_static_mount(FRONTEND_DIST / "assets"),
        )

        @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
        async def spa_fallback(full_path: str) -> FileResponse | JSONResponse:
            if full_path.startswith("api/"):
                return JSONResponse(
                    status_code=404,
                    content={"error": {"code": "not_found", "message": "Unknown API endpoint."}},
                )
            candidate = (FRONTEND_DIST / full_path).resolve()
            if (
                full_path
                and candidate.is_file()
                and str(candidate).startswith(str(FRONTEND_DIST.resolve()))
            ):
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


def _static_mount(path: Path):
    from fastapi.staticfiles import StaticFiles

    return StaticFiles(directory=path)


app = create_app()
