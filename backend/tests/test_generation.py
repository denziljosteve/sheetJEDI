"""End-to-end generation tests with a mocked provider (no real API calls)."""

from __future__ import annotations

import json

import httpx

from app.db.models import Solution
from tests.conftest import (
    chat_completion_response,
    configure_provider,
    install_mock_registry,
    valid_solution_json,
)


def _openai_ok_handler(content: str | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=chat_completion_response(content or valid_solution_json()))

    return handler


def _generate_body(**overrides):
    body = {
        "request": "Sum sales by month for January 2024",
        "platform": "excel",
        "task_type": "formula",
        "excel_version": "Microsoft 365",
        "skill_level": "intermediate",
        "provider": "groq",
        "model": "test-model",
    }
    body.update(overrides)
    return body


def test_generate_formula_solution(client):
    install_mock_registry(_openai_ok_handler())
    configure_provider(client, "groq", "gsk_test_key_12345")

    resp = client.post("/api/v1/solutions/generate", json=_generate_body())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    solution = body["solution"]
    assert solution["platform"] == "excel"
    assert solution["task_type"] == "formula"
    assert solution["formula"].startswith("=")
    assert solution["code"] is None
    assert solution["implementation_steps"][0]["instructions"]
    assert body["provider"] == "groq"
    assert body["fallback_used"] is False
    assert body["solution_id"] is not None
    assert body["usage"]["completion_tokens"] == 50


def test_generate_without_provider_configured(client):
    # No provider configured at all -> actionable 400.
    resp = client.post("/api/v1/solutions/generate", json=_generate_body(provider=None))
    assert resp.status_code == 502 or resp.status_code == 400
    code = resp.json()["error"]["code"]
    assert code in ("provider_not_configured",)
    assert "Settings" in resp.json()["error"]["message"]


def test_generate_without_model_returns_actionable_error(client):
    install_mock_registry(_openai_ok_handler())
    configure_provider(client, "groq", "gsk_test_key_12345", model=None)
    resp = client.post("/api/v1/solutions/generate", json=_generate_body(model="my-model"))
    # Per-request model override is used when provided.
    assert resp.status_code == 200

    # Without any model: actionable failure.
    resp2 = client.post(
        "/api/v1/solutions/generate", json=_generate_body(model=None, provider="groq")
    )
    assert resp2.status_code == 502
    assert resp2.json()["error"]["code"] == "model_not_configured"


def test_repair_roundtrip_on_invalid_output(client):
    """First response is garbage JSON; the repair attempt succeeds."""
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(
                200, json=chat_completion_response("Sure! Here is a formula: =SUM(A:A) ```broken")
            )
        return httpx.Response(200, json=chat_completion_response(valid_solution_json()))

    install_mock_registry(handler)
    configure_provider(client, "groq", "gsk_test_key_12345")

    resp = client.post("/api/v1/solutions/generate", json=_generate_body())
    assert resp.status_code == 200
    body = resp.json()
    assert len(calls) == 2  # initial + repair
    assert body["degraded"] is False
    assert body["solution"]["formula"].startswith("=")


def test_degraded_output_when_repair_also_fails(client):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=chat_completion_response("Not JSON at all, sorry."))

    install_mock_registry(handler)
    configure_provider(client, "groq", "gsk_test_key_12345")

    resp = client.post("/api/v1/solutions/generate", json=_generate_body())
    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is True
    assert body["degraded_notice"]
    assert "Not JSON at all" in body["solution"]["explanation"]
    assert any("validated" in w.lower() for w in body["solution"]["warnings"])


def test_destructive_code_triggers_warnings(client):
    vba = valid_solution_json(
        title="Delete old rows",
        summary="Deletes rows.",
        task_type="vba_macro",
        platform="excel",
        formula=None,
        code='Sub Clean()\n    Sheets("Data").Cells.Clear\nEnd Sub',
        code_language="vba",
    )
    install_mock_registry(_openai_ok_handler(vba))
    configure_provider(client, "groq", "gsk_test_key_12345")

    resp = client.post(
        "/api/v1/solutions/generate",
        json=_generate_body(task_type="vba_macro", provider="groq", model="test-model"),
    )
    assert resp.status_code == 200
    warnings = resp.json()["solution"]["warnings"]
    assert any("destructive" in w.lower() for w in warnings)


def test_fallback_provider_used_and_disclosed(client):
    """Primary (groq) fails with 500; configured fallback (openrouter) succeeds."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "groq.com" in str(request.url):
            return httpx.Response(500, json={"error": {"message": "boom"}})
        return httpx.Response(200, json=chat_completion_response(valid_solution_json()))

    install_mock_registry(handler)
    configure_provider(client, "groq", "gsk_test_key_12345")
    configure_provider(client, "openrouter", "or_key_12345")
    client.put(
        "/api/v1/settings/app",
        json={"fallback_provider": "openrouter", "fallback_model": "test-model"},
    )

    resp = client.post("/api/v1/solutions/generate", json=_generate_body())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fallback_used"] is True
    assert body["provider"] == "openrouter"
    assert any("fallback" in w.lower() for w in body["solution"]["warnings"])


def test_fallback_can_be_disabled_per_request(client):
    def handler(request: httpx.Request) -> httpx.Response:
        if "groq.com" in str(request.url):
            return httpx.Response(500, json={"error": {"message": "boom"}})
        return httpx.Response(200, json=chat_completion_response(valid_solution_json()))

    install_mock_registry(handler)
    configure_provider(client, "groq", "gsk_test_key_12345")
    configure_provider(client, "openrouter", "or_key_12345")
    client.put(
        "/api/v1/settings/app",
        json={"fallback_provider": "openrouter", "fallback_model": "test-model"},
    )

    resp = client.post("/api/v1/solutions/generate", json=_generate_body(use_fallback=False))
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "provider_error"


def test_auth_error_surfaces_actionable_message(client):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid api key"}})

    install_mock_registry(handler)
    configure_provider(client, "groq", "gsk_bad_key")
    resp = client.post("/api/v1/solutions/generate", json=_generate_body())
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "auth_error"
    assert "API key" in resp.json()["error"]["message"]


def test_history_persistence_respects_toggle(client, db):
    install_mock_registry(_openai_ok_handler())
    configure_provider(client, "groq", "gsk_test_key_12345")

    # Enabled by default -> history row created.
    resp = client.post("/api/v1/solutions/generate", json=_generate_body())
    solution_id = resp.json()["solution_id"]
    assert db.get(Solution, solution_id) is not None

    # Disabled -> no new row.
    client.put("/api/v1/settings/app", json={"history_enabled": False})
    resp2 = client.post("/api/v1/solutions/generate", json=_generate_body())
    assert resp2.json()["solution_id"] is None
    count_after = db.query(Solution).count()
    assert count_after == 1


def test_guided_fields_and_context_reach_prompt(client):
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content)
        captured["user"] = body["messages"][1]["content"]
        captured["system"] = body["messages"][0]["content"]
        return httpx.Response(200, json=chat_completion_response(valid_solution_json()))

    install_mock_registry(handler)
    configure_provider(client, "groq", "gsk_test_key_12345")

    client.post(
        "/api/v1/solutions/generate",
        json=_generate_body(
            guided={"lookup_column": "EmployeeID", "return_column": "Department"},
            context={
                "column_names": "EmployeeID, Department, Salary",
                "expected_result": "Department name per employee",
            },
        ),
    )
    user_prompt = captured["user"]
    assert "EmployeeID" in user_prompt
    assert "Department" in user_prompt
    assert "Microsoft 365" in user_prompt  # Excel version is part of the prompt


def test_validation_endpoint(client):
    payload = json.loads(valid_solution_json())
    resp = client.post("/api/v1/solutions/validate", json=payload)
    assert resp.status_code == 200
    assert resp.json()["valid"] is True

    bad = dict(payload)
    bad["code"] = "Sub Main()\nEnd Sub"
    bad.pop("code_language")
    resp2 = client.post("/api/v1/solutions/validate", json=bad)
    assert resp2.json()["valid"] is False
    assert resp2.json()["errors"]


def test_version_compatibility_in_prompt_for_old_excel(client):
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content)
        captured["system"] = body["messages"][0]["content"]
        return httpx.Response(200, json=chat_completion_response(valid_solution_json()))

    install_mock_registry(handler)
    configure_provider(client, "groq", "gsk_test_key_12345")
    client.post(
        "/api/v1/solutions/generate",
        json=_generate_body(excel_version="Excel 2016 or older"),
    )
    assert "Excel 2016 or older" in captured["system"]
    assert "XLOOKUP" in captured["system"]  # version rules mention it


def test_google_sheets_platform_prompt(client):
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content)
        captured["system"] = body["messages"][0]["content"]
        payload = json.loads(valid_solution_json(platform="google_sheets"))
        return httpx.Response(200, json=chat_completion_response(json.dumps(payload)))

    install_mock_registry(handler)
    configure_provider(client, "groq", "gsk_test_key_12345")
    resp = client.post(
        "/api/v1/solutions/generate",
        json=_generate_body(platform="google_sheets", excel_version=None),
    )
    assert resp.status_code == 200
    assert resp.json()["solution"]["platform"] == "google_sheets"
    assert "QUERY" in captured["system"]
