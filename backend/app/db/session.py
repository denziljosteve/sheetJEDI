"""SQLAlchemy engine and session management.

Default database is SQLite (local-first deployment). Setting
``SHEETJEDI_DATABASE_URL`` to a PostgreSQL URL switches the backend to
PostgreSQL without code changes (install the ``postgres`` extra).
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def _build_engine(settings: Settings) -> Engine:
    url = settings.database_url
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


def get_engine(settings: Settings | None = None) -> Engine:
    global _engine
    if _engine is None:
        _engine = _build_engine(settings or get_settings())
    return _engine


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=get_engine(settings), expire_on_commit=False, autoflush=False
        )
    return _SessionFactory


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def init_db(settings: Settings | None = None) -> None:
    """Create tables automatically in non-production environments.

    Production deployments must run Alembic migrations instead
    (``alembic upgrade head``) — see deploy.md.
    """
    settings = settings or get_settings()
    if settings.is_production:
        return
    from sqlalchemy import inspect

    from app.db import models

    engine = get_engine(settings)
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    required = {"provider_configs", "solutions", "files", "app_settings"}
    if not required.issubset(existing):
        models.Base.metadata.create_all(engine)


def database_ready() -> bool:
    """True when a trivial query succeeds (used by /api/v1/ready)."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def reset_engine() -> None:
    """Dispose and forget the engine (used by tests to swap databases)."""
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None
