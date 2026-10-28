"""Streaming generation, safety scanning, and rate limiting tests."""

from __future__ import annotations

import json
import time

import httpx

from app.core.ratelimit import SlidingWindowLimiter
from app.services.safety import scan_artifact
from tests.conftest import configure_provider, install_mock_registry, valid_solution_json

# ---------------------------------------------------------------------------
# Streaming (SSE)
# ---------------------------------------------------------------------------


def _sse_stream_handler(payload: str):
    def handler(request: httpx.Request) -> httpx.Response:
        lines = [
            'data: {"choices":[{"delta":{"content":' + json.dumps(payload[:20]) + "}}]}",
            'data: {"choices":[{"delta":{"content":' + json.dumps(payload[20:]) + "}}]}",
            "data: [DONE]",
        ]
        return httpx.Response(200, content=("\n".join(lines) + "\n").encode())

    return handler


def _parse_sse(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


def test_streaming_returns_deltas_and_solution(client):
    payload = valid_solution_json()
    install_mock_registry(_sse_stream_handler(payload))
    configure_provider(client, "groq", "gsk_test_key_12345")

    with client.stream(
        "POST",
        "/api/v1/solutions/generate/stream",
        json={
            "request": "Sum by month",
            "platform": "excel",
            "task_type": "formula",
            "provider": "groq",
            "model": "test-model",
        },
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = "".join(chunk for chunk in resp.iter_text())

    events = _parse_sse(body)
    kinds = [e["event"] for e in events]
    assert kinds[0] == "start"
    assert "delta" in kinds
    assert kinds[-1] == "done"
    deltas = "".join(e["text"] for e in events if e["event"] == "delta")
    assert deltas == payload
    done = next(e for e in events if e["event"] == "done")
    assert done["solution"]["formula"].startswith("=")
    assert done["degraded"] is False


def test_streaming_error_event_on_auth_failure(client):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    install_mock_registry(handler)
    configure_provider(client, "groq", "gsk_bad_key")

    resp = client.post(
        "/api/v1/solutions/generate/stream",
        json={
            "request": "Sum by month",
            "platform": "excel",
            "task_type": "formula",
            "provider": "groq",
            "model": "test-model",
        },
    )
    events = _parse_sse(resp.text)
    error_events = [e for e in events if e["event"] == "error"]
    assert error_events
    assert "API key" in error_events[0]["error"]["message"]


def test_streaming_degraded_on_invalid_output(client):
    def handler(request: httpx.Request) -> httpx.Response:
        lines = ['data: {"choices":[{"delta":{"content":"not json"}}]}', "data: [DONE]"]
        return httpx.Response(200, content=("\n".join(lines) + "\n").encode())

    install_mock_registry(handler)
    configure_provider(client, "groq", "gsk_test_key_12345")

    resp = client.post(
        "/api/v1/solutions/generate/stream",
        json={
            "request": "Sum by month",
            "platform": "excel",
            "task_type": "formula",
            "provider": "groq",
            "model": "test-model",
        },
    )
    events = _parse_sse(resp.text)
    done = next(e for e in events if e["event"] == "done")
    assert done["degraded"] is True


# ---------------------------------------------------------------------------
# Safety scanning
# ---------------------------------------------------------------------------


def test_safety_flags_vba_delete():
    warnings = scan_artifact(None, 'Range("A1").Delete', "vba")
    assert any("destructive" in w.lower() for w in warnings)


def test_safety_flags_vba_clear():
    warnings = scan_artifact(None, "Cells.ClearContents", "vba")
    assert warnings


def test_safety_flags_apps_script_delete_sheet():
    warnings = scan_artifact(None, "sheet.deleteSheet()", "apps_script")
    assert warnings


def test_safety_flags_apps_script_url_fetch():
    warnings = scan_artifact(None, "UrlFetchApp.fetch(url)", "apps_script")
    assert any("external" in w.lower() for w in warnings)


def test_safety_flags_office_script_delete():
    code = "range.delete(ExcelScript.ScriptDeleteShiftDirection.shiftUp)"
    warnings = scan_artifact(None, code, "office_script")
    assert warnings


def test_safety_flags_importrange_in_formula():
    warnings = scan_artifact('=IMPORTRANGE("https://x", "A1")', None, None)
    assert any("grant" in w.lower() or "access" in w.lower() for w in warnings)


def test_safe_code_has_no_warnings():
    warnings = scan_artifact(
        '=SUMIFS(C:C,A:A,">="&DATE(2024,1,1))',
        'Sub Hello()\n  MsgBox "hi"\nEnd Sub',
        "vba",
    )
    assert warnings == []


def test_warnings_deduplicated():
    warnings = scan_artifact(None, "Cells.Clear\nRange.ClearContents", "vba")
    assert len(warnings) == len(set(warnings))


# ---------------------------------------------------------------------------
# Rate limiter (unit)
# ---------------------------------------------------------------------------


def test_sliding_window_limiter_blocks_after_limit():
    limiter = SlidingWindowLimiter(window_seconds=60, max_requests=3)
    assert all(limiter.allow("ip1") for _ in range(3))
    assert limiter.allow("ip1") is False
    # Different client is unaffected.
    assert limiter.allow("ip2") is True


def test_sliding_window_limiter_window_expiry():
    limiter = SlidingWindowLimiter(window_seconds=0, max_requests=1)
    assert limiter.allow("ip") is True
    time.sleep(0.05)  # exceed Windows' ~15ms timer granularity
    assert limiter.allow("ip") is True  # window of 0s -> previous hit expired
