"""Provider adapter tests with mocked HTTP (no real network calls)."""

from __future__ import annotations

import httpx
import pytest

from app.providers.base import ChatMessage, GenerationOptions, RuntimeConfig
from app.providers.errors import ProviderError, error_from_exception, error_from_response
from app.providers.registry import PROVIDER_ORDER, build_registry
from tests.conftest import (
    anthropic_message_response,
    chat_completion_response,
    configure_provider,
    install_mock_registry,
    valid_solution_json,
)

MESSAGES = [
    ChatMessage(role="system", content="system"),
    ChatMessage(role="user", content="user"),
]
OPTIONS = GenerationOptions(model="test-model")


def _json_response(status: int, payload: dict) -> httpx.Response:
    return httpx.Response(status_code=status, json=payload)


# ---------------------------------------------------------------------------
# Registry metadata
# ---------------------------------------------------------------------------


def test_registry_contains_all_six_providers():
    registry = build_registry()
    assert set(PROVIDER_ORDER) == set(registry.keys())
    assert len(registry) == 6


def test_registry_protocols():
    registry = build_registry()
    assert registry["groq"].protocol == "openai_chat"
    assert registry["openrouter"].protocol == "openai_chat"
    assert registry["openai"].protocol == "openai_chat"
    assert registry["omniroute"].protocol == "openai_chat"
    assert registry["anthropic"].protocol == "anthropic_messages"
    assert registry["longcat"].protocol == "anthropic_messages"


def test_omniroute_requires_custom_base_url_capability():
    registry = build_registry()
    assert registry["omniroute"].capabilities.custom_base_url is True


def test_longcat_default_base_url():
    registry = build_registry()
    assert registry["longcat"].default_base_url == "https://api.longcat.chat/anthropic"


# ---------------------------------------------------------------------------
# Model discovery (OpenAI-compatible + Anthropic)
# ---------------------------------------------------------------------------


def test_list_models_openai_compatible():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models")
        assert request.headers["Authorization"] == "Bearer sk-test-1234"
        return _json_response(200, {"data": [{"id": "model-b"}, {"id": "model-a"}]})

    registry = install_mock_registry(handler)
    adapter = registry["groq"]
    import asyncio

    models = asyncio.run(adapter.list_models(RuntimeConfig(api_key="sk-test-1234")))
    assert [m.id for m in models] == ["model-a", "model-b"]  # sorted


def test_list_models_openrouter_includes_context_window():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            200,
            {"data": [{"id": "x/llama", "name": "Llama", "context_length": 131072}]},
        )

    registry = install_mock_registry(handler)
    adapter = registry["openrouter"]
    import asyncio

    models = asyncio.run(adapter.list_models(RuntimeConfig(api_key="or-key")))
    assert models[0].context_window == 131072


def test_list_models_anthropic_protocol():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        assert request.headers["x-api-key"] == "ak-test"
        assert request.headers["anthropic-version"]
        return _json_response(200, {"data": [{"id": "claude-x", "display_name": "Claude X"}]})

    registry = install_mock_registry(handler)
    adapter = registry["anthropic"]
    import asyncio

    models = asyncio.run(adapter.list_models(RuntimeConfig(api_key="ak-test")))
    assert models[0].id == "claude-x"
    assert models[0].name == "Claude X"


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def test_generate_openai_compatible():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        return _json_response(200, chat_completion_response(valid_solution_json()))

    registry = install_mock_registry(handler)
    adapter = registry["groq"]
    import asyncio

    resp = asyncio.run(adapter.generate(RuntimeConfig(api_key="k"), MESSAGES, OPTIONS))
    assert '"title"' in resp.text
    assert resp.usage is not None and resp.usage.prompt_tokens == 100


def test_generate_anthropic_protocol():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/messages"
        import json as _json

        body = _json.loads(request.content)
        assert body["system"] == "system"  # system prompt is separate in Anthropic protocol
        assert body["max_tokens"] > 0
        return _json_response(200, anthropic_message_response(valid_solution_json()))

    registry = install_mock_registry(handler)
    adapter = registry["anthropic"]
    import asyncio

    resp = asyncio.run(adapter.generate(RuntimeConfig(api_key="k"), MESSAGES, OPTIONS))
    assert '"platform"' in resp.text


def test_generate_json_mode_payload_and_400_fallback():
    """response_format is retried without when a gateway rejects it."""
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content)
        seen.append(body)
        if "response_format" in body:
            return _json_response(400, {"error": {"message": "response_format is not supported"}})
        return _json_response(200, chat_completion_response(valid_solution_json()))

    registry = install_mock_registry(handler)
    adapter = registry["groq"]
    import asyncio

    options = GenerationOptions(model="test-model", json_mode=True)
    resp = asyncio.run(adapter.generate(RuntimeConfig(api_key="k"), MESSAGES, options))
    assert "response_format" in seen[0]
    assert "response_format" not in seen[1]
    assert '"title"' in resp.text


def test_generate_empty_choices_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(200, {"choices": []})

    registry = install_mock_registry(handler)
    adapter = registry["groq"]
    import asyncio

    with pytest.raises(ProviderError) as exc:
        asyncio.run(adapter.generate(RuntimeConfig(api_key="k"), MESSAGES, OPTIONS))
    assert exc.value.code == "malformed_response"


def test_generate_truncated_response_reported():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            200,
            {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]},
        )

    registry = install_mock_registry(handler)
    adapter = registry["groq"]
    import asyncio

    with pytest.raises(ProviderError) as exc:
        asyncio.run(adapter.generate(RuntimeConfig(api_key="k"), MESSAGES, OPTIONS))
    assert exc.value.code == "response_truncated"


# ---------------------------------------------------------------------------
# Error normalization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected_code", "retryable"),
    [
        (401, "auth_error", False),
        (403, "permission_error", False),
        (404, "not_found", False),
        (429, "rate_limited", True),
        (500, "provider_error", True),
        (503, "provider_error", True),
    ],
)
def test_error_normalization_from_status(status, expected_code, retryable):
    resp = httpx.Response(status, json={"error": {"message": "upstream said no"}})
    err = error_from_response(resp, "groq")
    assert err.code == expected_code
    assert err.retryable == retryable
    assert "groq" in err.message


def test_error_timeout_is_retryable():
    err = error_from_exception(httpx.ReadTimeout("timed out"), "openai")
    assert err.code == "timeout"
    assert err.retryable is True


def test_error_connection_is_retryable():
    err = error_from_exception(httpx.ConnectError("refused"), "openai")
    assert err.code == "connection_error"
    assert err.retryable is True


def test_auth_error_message_is_actionable_and_keyless():
    resp = httpx.Response(401, json={"error": {"message": "invalid api key sk-secret-xyz"}})
    err = error_from_response(resp, "openai")
    assert "API key" in err.message
    # The provider's raw message (which can contain the key) is not surfaced.
    assert "sk-secret-xyz" not in err.message


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------


def test_connection_test_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(200, {"data": [{"id": "m1"}, {"id": "m2"}]})

    registry = install_mock_registry(handler)
    adapter = registry["openai"]
    import asyncio

    result = asyncio.run(adapter.test_connection(RuntimeConfig(api_key="k")))
    assert result.ok is True
    assert result.models_count == 2


def test_connection_test_failure_reports_auth_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(401, {"error": {"message": "bad key"}})

    registry = install_mock_registry(handler)
    adapter = registry["openai"]
    import asyncio

    result = asyncio.run(adapter.test_connection(RuntimeConfig(api_key="k")))
    assert result.ok is False
    assert "authentication" in result.message


def test_connection_test_without_key_is_unconfigured():
    adapter = build_registry()["openai"]
    import asyncio

    result = asyncio.run(adapter.test_connection(RuntimeConfig(api_key=None)))
    assert result.ok is False
    assert "API key" in result.message


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


def test_stream_openai_compatible_yields_deltas():
    def handler(request: httpx.Request) -> httpx.Response:
        lines = [
            'data: {"choices":[{"delta":{"content":"=SUM"}}]}',
            'data: {"choices":[{"delta":{"content":"(A:A)"}}]}',
            "data: [DONE]",
        ]
        return httpx.Response(200, content=("\n".join(lines) + "\n").encode())

    registry = install_mock_registry(handler)
    adapter = registry["groq"]
    import asyncio

    async def collect():
        return [d async for d in adapter.stream(RuntimeConfig(api_key="k"), MESSAGES, OPTIONS)]

    assert asyncio.run(collect()) == ["=SUM", "(A:A)"]


def test_stream_anthropic_yields_deltas():
    def handler(request: httpx.Request) -> httpx.Response:
        lines = [
            'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"=X"}}',
            'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"LOOKUP"}}',
        ]
        return httpx.Response(200, content=("\n".join(lines) + "\n").encode())

    registry = install_mock_registry(handler)
    adapter = registry["longcat"]
    import asyncio

    async def collect():
        return [d async for d in adapter.stream(RuntimeConfig(api_key="k"), MESSAGES, OPTIONS)]

    assert asyncio.run(collect()) == ["=X", "LOOKUP"]


# ---------------------------------------------------------------------------
# API-level provider endpoints
# ---------------------------------------------------------------------------


def test_list_providers_endpoint(client):
    resp = client.get("/api/v1/providers")
    assert resp.status_code == 200
    providers = resp.json()
    assert len(providers) == 6
    assert all(p["config_status"] == "unconfigured" for p in providers)
    # No credential material may appear anywhere in the payload.
    for p in providers:
        assert "api_key" not in p
        assert "api_key_encrypted" not in p
    assert "gsk_" not in resp.text and "sk-" not in resp.text.replace("task-", "")


def test_provider_config_masks_key(client):
    resp = client.put(
        "/api/v1/settings/providers/groq",
        json={"api_key": "gsk_abcdef1234567890", "default_model": "llama-3.3-70b"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["api_key_hint"] == "••••7890"
    assert "gsk_abcdef1234567890" not in resp.text
    assert body["config_status"] == "configured"

    # Listing providers also never exposes the raw key.
    listing = client.get("/api/v1/providers").text
    assert "gsk_abcdef1234567890" not in listing


def test_provider_key_not_returned_in_database_as_plaintext(client, db):
    from app.services import settings_service

    client.put(
        "/api/v1/settings/providers/openai",
        json={"api_key": "sk-supersecret-key-123456"},
    )
    row = settings_service.get_provider_row(db, "openai")
    assert row is not None
    assert "sk-supersecret-key-123456" not in (row.api_key_encrypted or "")
    runtime = settings_service.resolve_runtime(db, "openai")
    assert runtime.api_key == "sk-supersecret-key-123456"  # decryptable server-side


def test_custom_base_url_rejected_for_fixed_providers(client):
    resp = client.put(
        "/api/v1/settings/providers/openai",
        json={"api_key": "sk-x", "base_url": "https://evil.example.com/v1"},
    )
    assert resp.status_code == 422


def test_custom_base_url_allowed_for_omniroute(client):
    resp = client.put(
        "/api/v1/settings/providers/omniroute",
        json={"base_url": "http://localhost:9999/v1", "default_model": "claude-x"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["base_url_override"] == "http://localhost:9999/v1"


def test_clear_api_key(client):
    client.put("/api/v1/settings/providers/groq", json={"api_key": "gsk_key123456789"})
    resp = client.put("/api/v1/settings/providers/groq", json={"clear_api_key": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["api_key_hint"] is None
    assert body["config_status"] == "unconfigured"


def test_unknown_provider_404(client):
    resp = client.put("/api/v1/settings/providers/nope", json={"api_key": "x"})
    assert resp.status_code == 404


def test_models_endpoint_requires_configuration(client):
    resp = client.get("/api/v1/providers/groq/models")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "provider_not_configured"


def test_models_endpoint_live_and_cached(client):
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(200, {"data": [{"id": "llama-3.3-70b"}, {"id": "mixtral"}]})

    install_mock_registry(handler)
    configure_provider(client, "groq", "gsk_test_key_1234")
    resp = client.get("/api/v1/providers/groq/models")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "live"
    assert {m["id"] for m in body["models"]} == {"llama-3.3-70b", "mixtral"}

    resp2 = client.get("/api/v1/providers/groq/models")
    assert resp2.json()["source"] == "cache"


def test_test_endpoint_records_real_failure(client):
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(401, {"error": {"message": "bad credentials"}})

    install_mock_registry(handler)
    configure_provider(client, "groq", "gsk_wrong_key")
    resp = client.post("/api/v1/providers/groq/test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    # Status reflects the failed test — never faked as "tested".
    providers = client.get("/api/v1/providers").json()
    groq = next(p for p in providers if p["name"] == "groq")
    assert groq["config_status"] == "failed"
    assert groq["last_test_message"]


def test_test_endpoint_records_success(client):
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(200, {"data": [{"id": "m1"}]})

    install_mock_registry(handler)
    configure_provider(client, "openrouter", "or-key-123456")
    resp = client.post("/api/v1/providers/openrouter/test")
    body = resp.json()
    assert body["ok"] is True
    assert body["models_count"] == 1
    providers = client.get("/api/v1/providers").json()
    openrouter = next(p for p in providers if p["name"] == "openrouter")
    assert openrouter["config_status"] == "tested"
    assert openrouter["last_tested_at"] is not None
