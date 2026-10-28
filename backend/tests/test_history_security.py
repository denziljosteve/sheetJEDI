"""History endpoints and security unit tests."""

from __future__ import annotations

import httpx
import pytest
from cryptography.fernet import Fernet

from app.core import security
from app.core.config import get_settings
from app.core.errors import AppError
from tests.conftest import (
    chat_completion_response,
    configure_provider,
    install_mock_registry,
    valid_solution_json,
)

# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def _generate(client):
    install_mock_registry(
        lambda request: httpx.Response(200, json=chat_completion_response(valid_solution_json()))
    )
    configure_provider(client, "groq", "gsk_test_key_12345")
    resp = client.post(
        "/api/v1/solutions/generate",
        json={
            "request": "Sum by month",
            "platform": "excel",
            "task_type": "formula",
            "provider": "groq",
            "model": "test-model",
        },
    )
    assert resp.status_code == 200
    return resp.json()


def test_history_list_get_delete(client):
    body = _generate(client)
    solution_id = body["solution_id"]

    listing = client.get("/api/v1/history").json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == solution_id
    assert listing["items"][0]["title"]
    assert listing["items"][0]["request_preview"]

    detail = client.get(f"/api/v1/history/{solution_id}")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["solution"]["formula"].startswith("=")
    assert detail_body["request"]["request_text"] == "Sum by month"

    del_resp = client.delete(f"/api/v1/history/{solution_id}")
    assert del_resp.status_code == 204
    assert client.get(f"/api/v1/history/{solution_id}").status_code == 404
    assert client.get("/api/v1/history").json()["total"] == 0


def test_history_not_found(client):
    assert client.get("/api/v1/history/deadbeef").status_code == 404
    assert client.delete("/api/v1/history/deadbeef").status_code == 404


def test_history_pagination(client):
    for _ in range(3):
        _generate(client)
    page = client.get("/api/v1/history?limit=2&offset=0").json()
    assert len(page["items"]) == 2
    assert page["total"] == 3
    page2 = client.get("/api/v1/history?limit=2&offset=2").json()
    assert len(page2["items"]) == 1


# ---------------------------------------------------------------------------
# Security unit tests
# ---------------------------------------------------------------------------


def test_encrypt_decrypt_roundtrip(client):
    cipher = security.encrypt_secret("sk-my-secret-key", get_settings())
    assert "sk-my-secret-key" not in cipher
    plain = security.decrypt_secret(cipher, get_settings())
    assert plain == "sk-my-secret-key"


def test_mask_key():
    assert security.mask_key("gsk_abcdef123456") == "••••3456"
    assert security.mask_key("ab") == "••••"
    assert security.mask_key("") == ""


def test_redact_patterns():
    from app.core.logging import redact

    assert redact("key is sk-abcdefghijklmnop") == "key is ***REDACTED***"
    assert redact("gsk_1234567890abcd") == "***REDACTED***"
    assert redact("ak_1234567890abcd") == "***REDACTED***"
    assert redact("Authorization: Bearer secret.token.value123") == "Authorization: ***REDACTED***"
    assert redact('{"api_key": "super-secret-value"}') == '{"api_key": "***REDACTED***"}'


def test_registered_secrets_redacted(client):
    from app.core.logging import redact, register_secret

    register_secret("my-custom-provider-key-9999")
    try:
        assert "my-custom-provider-key-9999" not in redact("using my-custom-provider-key-9999 now")
    finally:
        from app.core import logging as core_logging

        core_logging._registered_secrets.discard("my-custom-provider-key-9999")


def test_production_requires_master_key(monkeypatch, tmp_path):
    monkeypatch.setenv("SHEETJEDI_ENV", "production")
    monkeypatch.setenv("SHEETJEDI_SECRET_KEY", "")
    monkeypatch.setattr(security, "_fernet", None)
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(AppError) as exc:
            security.encrypt_secret("k" * 20, get_settings())
        assert exc.value.code == "config_error"
    finally:
        monkeypatch.delenv("SHEETJEDI_ENV", raising=False)
        get_settings.cache_clear()
        security._fernet = None


def test_dev_master_key_generated_when_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("SHEETJEDI_SECRET_KEY", "")
    monkeypatch.setattr(security, "_KEY_FILE", tmp_path / ".master_key")
    monkeypatch.setattr(security, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(security, "_fernet", None)
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        fernet = security.get_fernet(get_settings())
        assert (tmp_path / ".master_key").exists()
        # Deterministic: same key reused on second call.
        security._fernet = None
        fernet2 = security.get_fernet(get_settings())
        assert fernet.decrypt(fernet2.encrypt(b"hello")) == b"hello"
    finally:
        get_settings.cache_clear()
        security._fernet = None


def test_decrypt_with_wrong_key_fails_loudly(client, monkeypatch):
    cipher = security.encrypt_secret("sk-secret-value", get_settings())
    # Simulate a changed/lost master key: swap the cached Fernet to a new key.
    monkeypatch.setattr(security, "_fernet", Fernet(Fernet.generate_key()))
    with pytest.raises(AppError) as exc:
        security.decrypt_secret(cipher, get_settings())
    assert exc.value.code == "secret_decryption_failed"
