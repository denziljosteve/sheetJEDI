"""Health, readiness, and error-envelope tests."""

from __future__ import annotations


def test_health_returns_ok(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_ready_reports_database_ok(client):
    resp = client.get("/api/v1/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"


def test_unknown_api_path_returns_error_envelope(client):
    resp = client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] in ("http_error", "not_found")


def test_validation_error_envelope(client):
    resp = client.post("/api/v1/solutions/generate", json={"request": "x"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["details"], list)


def test_request_id_header_present(client):
    resp = client.get("/api/v1/health")
    assert "x-request-id" in resp.headers


def test_request_id_is_propagated(client):
    resp = client.get("/api/v1/health", headers={"X-Request-ID": "req-123"})
    assert resp.headers["x-request-id"] == "req-123"


def test_openapi_schema_available(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    assert "/api/v1/solutions/generate" in spec["paths"]
    assert "/api/v1/providers" in spec["paths"]
