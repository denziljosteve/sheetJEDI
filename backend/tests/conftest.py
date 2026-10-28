"""Shared pytest fixtures.

Tests run against an isolated temporary SQLite database and a mocked HTTP
transport — no real provider is ever contacted unless a test is explicitly
marked ``live`` AND the corresponding credential env var is present.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core import security
from app.core.config import get_settings
from app.db import session as db_session
from app.providers import registry as registry_module
from app.services import settings_service


@pytest.fixture(scope="session")
def fernet_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture()
def client(tmp_path, monkeypatch, fernet_key) -> Iterator[TestClient]:
    """TestClient wired to a fresh temp database and a fixed master key."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SHEETJEDI_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SHEETJEDI_SECRET_KEY", fernet_key)
    monkeypatch.setenv("SHEETJEDI_RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("SHEETJEDI_HISTORY_ENABLED", "true")
    monkeypatch.setenv("SHEETJEDI_ENV", "development")

    get_settings.cache_clear()
    security._fernet = None
    db_session.reset_engine()
    settings_service.invalidate_model_cache()
    registry_module._registry = None

    from app.main import app

    db_session.init_db(get_settings())

    with TestClient(app) as test_client:
        yield test_client

    db_session.reset_engine()
    registry_module._registry = None
    get_settings.cache_clear()
    security._fernet = None


@pytest.fixture()
def db(client) -> Iterator[Any]:
    """A database session bound to the test database."""
    session = db_session.get_session_factory(get_settings())()
    try:
        yield session
    finally:
        session.close()


def mock_http_client(handler) -> httpx.AsyncClient:
    """Build an AsyncClient with a MockTransport for provider adapters."""
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport)


def install_mock_registry(handler) -> dict[str, Any]:
    """Point the global provider registry at a mocked HTTP transport.

    Returns the mocked registry so tests can grab adapters bound to it.
    """
    client = mock_http_client(handler)
    return registry_module.get_registry(client)


def reset_registry() -> None:
    registry_module._registry = None


# ---------------------------------------------------------------------------
# Reusable payloads
# ---------------------------------------------------------------------------


def valid_solution_json(**overrides: Any) -> str:
    payload: dict[str, Any] = {
        "title": "Sum sales by month",
        "summary": "SUMIFS over a date-bounded sales column.",
        "platform": "excel",
        "task_type": "formula",
        "task_category": "conditional calculations",
        "formula": (
            '=SUMIFS(C:C,A:A,">="&EOMONTH(DATE(2024,1,1),-1)+1,A:A,"<="&EOMONTH(DATE(2024,1,1),0))'
        ),
        "code": None,
        "code_language": None,
        "required_version": "Excel 2007+",
        "assumptions": ["Sales amounts live in column C."],
        "prerequisites": ["A workbook with a Date column A and Amount column C."],
        "explanation": "SUMIFS adds amounts whose date falls within the month.",
        "implementation_steps": [
            {
                "title": "Enter the formula",
                "instructions": "Type the formula into the target cell and press Enter.",
                "cell_references": ["E1"],
                "code_location": None,
            }
        ],
        "example_input": "A: 2024-01-15, C: 100",
        "expected_output": "The total of January sales.",
        "alternative_solutions": [],
        "common_errors": [
            {"error": "#VALUE!", "cause": "Text in the sum range.", "solution": "Clean the column."}
        ],
        "troubleshooting": ["Check that dates are real dates, not text."],
        "warnings": [],
        "confidence_notes": None,
    }
    payload.update(overrides)
    return json.dumps(payload)


def chat_completion_response(content: str, model: str = "test-model") -> dict[str, Any]:
    return {
        "id": "chatcmpl-1",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }


def anthropic_message_response(content: str, model: str = "test-model") -> dict[str, Any]:
    return {
        "id": "msg_1",
        "model": model,
        "content": [{"type": "text", "text": content}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }


def configure_provider(
    client: TestClient, provider: str, api_key: str, model: str | None = "test-model"
) -> None:
    """Convenience: configure a provider through the public API."""
    resp = client.put(
        f"/api/v1/settings/providers/{provider}",
        json={"api_key": api_key, "default_model": model},
    )
    assert resp.status_code == 200, resp.text
