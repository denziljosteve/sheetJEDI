"""Provider registry.

Implementation order and verification status (see decision.md D-004):

1. Groq         — OpenAI-compatible; endpoint verified reachable (401 unauth).
2. OpenRouter   — OpenAI-compatible; public /models verified (HTTP 200).
3. OpenAI       — OpenAI-compatible; endpoint verified reachable (401 unauth).
4. Anthropic    — Messages API; endpoint verified reachable (401 unauth).
5. OmniRoute    — self-hosted open-source AI gateway (github.com/NFTHiKe/OmniRoute)
                  exposing OpenAI-compatible APIs. Implemented behind a custom
                  base URL; requires a user-run instance to connect.
6. LongCat      — Meituan's LongCat API platform; Anthropic-compatible endpoint
                  at https://api.longcat.chat/anthropic verified reachable
                  (401 unauth; the OpenAI-style path 404s).

No adapter here claims a live authenticated connection — those require user
API keys and are only reported as "tested" after an actual successful test.
"""

from __future__ import annotations

import httpx

from app.providers.anthropic_compat import AnthropicMessagesAdapter
from app.providers.base import ProviderAdapter
from app.providers.openai_compat import OpenAIChatAdapter

PROVIDER_ORDER = ["groq", "openrouter", "openai", "anthropic", "omniroute", "longcat"]


def build_registry(client: httpx.AsyncClient | None = None) -> dict[str, ProviderAdapter]:
    adapters: list[ProviderAdapter] = [
        OpenAIChatAdapter(
            name="groq",
            display_name="Groq",
            default_base_url="https://api.groq.com/openai/v1",
            json_mode=True,
            status_note="Fast inference on Groq LPUs. Uses the OpenAI-compatible API.",
            verification_status="protocol_verified",
            docs_url="https://console.groq.com/docs",
            client=client,
        ),
        OpenAIChatAdapter(
            name="openrouter",
            display_name="OpenRouter",
            default_base_url="https://openrouter.ai/api/v1",
            json_mode=True,
            extra_headers={"X-Title": "sheetJEDI"},
            status_note="Unified gateway to 200+ models. Public model list verified.",
            verification_status="protocol_verified",
            docs_url="https://openrouter.ai/docs",
            client=client,
        ),
        OpenAIChatAdapter(
            name="openai",
            display_name="OpenAI",
            default_base_url="https://api.openai.com/v1",
            json_mode=True,
            status_note="OpenAI API (GPT models) via the standard chat-completions endpoint.",
            verification_status="protocol_verified",
            docs_url="https://platform.openai.com/docs",
            client=client,
        ),
        AnthropicMessagesAdapter(
            name="anthropic",
            display_name="Anthropic (Claude)",
            default_base_url="https://api.anthropic.com",
            status_note="Anthropic Messages API (Claude models).",
            verification_status="protocol_verified",
            docs_url="https://docs.anthropic.com/en/api/overview",
            client=client,
        ),
        OpenAIChatAdapter(
            name="omniroute",
            display_name="OmniRoute",
            default_base_url="http://localhost:3000/v1",
            custom_base_url=True,
            json_mode=False,
            status_note=(
                "OmniRoute is a self-hosted AI gateway exposing OpenAI-compatible APIs. "
                "Set Base URL to your running instance (e.g. http://localhost:3000/v1 "
                "or your deployed gateway). Connection requires your own instance."
            ),
            verification_status="protocol_verified_host_required",
            docs_url="https://github.com/NFTHiKe/OmniRoute",
            client=client,
        ),
        AnthropicMessagesAdapter(
            name="longcat",
            display_name="LongCat",
            default_base_url="https://api.longcat.chat/anthropic",
            custom_base_url=True,
            status_note=(
                "Meituan's LongCat API platform via its Anthropic-compatible endpoint. "
                "API keys are issued at longcat.chat."
            ),
            verification_status="protocol_verified",
            docs_url="https://longcat.chat",
            client=client,
        ),
    ]
    return {a.name: a for a in adapters}


_registry: dict[str, ProviderAdapter] | None = None


def get_registry(client: httpx.AsyncClient | None = None) -> dict[str, ProviderAdapter]:
    global _registry
    if _registry is None or client is not None:
        _registry = build_registry(client)
    return _registry
