"""Optional live provider smoke tests.

These are EXCLUDED from ordinary runs by default. To execute them:

    set SHEETJEDI_LIVE_TESTS=1
    set GROQ_API_KEY=gsk_...        (or OPENAI_API_KEY / OPENROUTER_API_KEY /
                                     ANTHROPIC_API_KEY / LONGCAT_API_KEY)
    pytest -m live

They make real network calls and may incur provider costs. They only test
model discovery + a tiny connection check — never paid generation.
"""

from __future__ import annotations

import os

import pytest

from app.providers.base import RuntimeConfig
from app.providers.registry import build_registry

pytestmark = pytest.mark.live

_LIVE_ENABLED = os.environ.get("SHEETJEDI_LIVE_TESTS") == "1"

_ENV_KEYS = {
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "longcat": "LONGCAT_API_KEY",
}


def _skip_unless(provider: str) -> str | None:
    if not _LIVE_ENABLED:
        return "live tests disabled (set SHEETJEDI_LIVE_TESTS=1 to enable)"
    key = os.environ.get(_ENV_KEYS[provider])
    if not key:
        return f"{_ENV_KEYS[provider]} not set"
    return None


@pytest.mark.parametrize("provider", ["groq", "openrouter", "openai", "anthropic", "longcat"])
async def test_live_model_discovery(provider: str):
    reason = _skip_unless(provider)
    if reason:
        pytest.skip(reason)
    adapter = build_registry()[provider]
    runtime = RuntimeConfig(api_key=os.environ[_ENV_KEYS[provider]], timeout_seconds=30.0)
    result = await adapter.test_connection(runtime)
    assert result.ok, f"live connection test failed: {result.message}"
    assert result.models_count is not None and result.models_count > 0
