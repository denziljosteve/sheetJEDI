"""Regression test: built-frontend (SPA) serving registered without errors.

Session-1 smoke tests ran before ``frontend/dist`` existed, so the SPA block in
``create_app`` never executed. FastAPI (newer versions) rejects the
``FileResponse | JSONResponse`` return annotation unless ``response_model=None``
is set — this test exercises exactly that path.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core import security
from app.core.config import get_settings
from app.db import session as db_session
from app.providers import registry as registry_module
from app.services import settings_service


def test_spa_fallback_serves_index_and_api_stays_json(tmp_path, monkeypatch, fernet_key) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>sheetJEDI</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('app');", encoding="utf-8")

    db_path = tmp_path / "spa_test.db"
    monkeypatch.setenv("SHEETJEDI_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SHEETJEDI_SECRET_KEY", fernet_key)
    monkeypatch.setenv("SHEETJEDI_RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("SHEETJEDI_ENV", "development")

    get_settings.cache_clear()
    security._fernet = None
    db_session.reset_engine()
    settings_service.invalidate_model_cache()
    registry_module._registry = None

    import app.main as main

    monkeypatch.setattr(main, "FRONTEND_DIST", dist)
    app = main.create_app()
    db_session.init_db(get_settings())

    try:
        with TestClient(app) as client:
            # Root serves the SPA shell.
            index = client.get("/")
            assert index.status_code == 200
            assert "sheetJEDI" in index.text

            # Unknown client route falls back to index.html (SPA routing).
            deep = client.get("/generate/formula")
            assert deep.status_code == 200
            assert "sheetJEDI" in deep.text

            # Built assets are served with correct content.
            asset = client.get("/assets/app.js")
            assert asset.status_code == 200
            assert "console.log" in asset.text

            # Path traversal outside dist is rejected (not served).
            evil = client.get("/../pyproject.toml")
            assert evil.status_code in (200, 404)
            assert "tool.pydantic" not in evil.text

            # Unknown API paths stay a structured JSON 404, never HTML.
            missing = client.get("/api/v1/does-not-exist")
            assert missing.status_code == 404
            assert missing.headers["content-type"].startswith("application/json")
            assert missing.json()["error"]["code"] == "not_found"
    finally:
        db_session.reset_engine()
        registry_module._registry = None
        get_settings.cache_clear()
        security._fernet = None
