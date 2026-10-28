"""Adapter for the Anthropic Messages API (Anthropic and LongCat).

Anthropic's protocol differs materially from OpenAI's: ``x-api-key`` header,
a mandatory ``anthropic-version`` header, system prompts passed outside the
message list, and a required ``max_tokens``. LongCat (Meituan) exposes an
Anthropic-compatible endpoint at ``https://api.longcat.chat/anthropic``.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.providers.base import (
    ChatMessage,
    GenerationOptions,
    ModelInfo,
    ProviderAdapter,
    ProviderCapabilities,
    ProviderResponse,
    RuntimeConfig,
    UsageInfo,
)
from app.providers.errors import (
    ProviderError,
    error_from_exception,
    error_from_response,
)

ANTHROPIC_VERSION = "2023-06-01"


class AnthropicMessagesAdapter(ProviderAdapter):
    protocol = "anthropic_messages"

    def __init__(
        self,
        *,
        name: str,
        display_name: str,
        default_base_url: str,
        custom_base_url: bool = False,
        status_note: str | None = None,
        verification_status: str = "untested",
        docs_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(client)
        self.name = name
        self.display_name = display_name
        self.default_base_url = default_base_url
        self.capabilities = ProviderCapabilities(
            streaming=True,
            model_discovery=True,
            json_mode=False,  # no native json_object mode; JSON is prompt-driven
            custom_base_url=custom_base_url,
        )
        self.status_note = status_note
        self.verification_status = verification_status
        self.docs_url = docs_url

    def auth_headers(self, config: RuntimeConfig) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": ANTHROPIC_VERSION,
        }
        if config.api_key:
            headers["x-api-key"] = config.api_key
        return headers

    async def list_models(self, config: RuntimeConfig) -> list[ModelInfo]:
        base = self.effective_base_url(config)
        client = self._get_client(config)
        try:
            resp = await client.get(f"{base}/v1/models", headers=self.auth_headers(config))
            if resp.status_code >= 400:
                raise error_from_response(resp, self.name)
            payload = resp.json()
        except ProviderError:
            raise
        except Exception as exc:
            raise error_from_exception(exc, self.name) from exc
        finally:
            await self._aclose(client)

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise ProviderError(
                "malformed_response",
                f"{self.name}: unexpected model list response.",
                provider=self.name,
            )
        models: list[ModelInfo] = []
        for item in data:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            models.append(
                ModelInfo(
                    id=str(item["id"]),
                    name=str(item.get("display_name") or item["id"]),
                    context_window=None,
                    capabilities={},
                )
            )
        return sorted(models, key=lambda m: m.id)

    def _split_system(self, messages: list[ChatMessage]) -> tuple[str | None, list[dict]]:
        system_parts = [m.content for m in messages if m.role == "system"]
        chat = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]
        system = "\n\n".join(system_parts) if system_parts else None
        return system, chat

    async def generate(
        self,
        config: RuntimeConfig,
        messages: list[ChatMessage],
        options: GenerationOptions,
    ) -> ProviderResponse:
        base = self.effective_base_url(config)
        system, chat = self._split_system(messages)
        payload: dict[str, Any] = {
            "model": options.model,
            "messages": chat,
            "max_tokens": options.max_tokens,
            "temperature": options.temperature,
        }
        if system:
            payload["system"] = system

        client = self._get_client(config)
        try:
            resp = await client.post(
                f"{base}/v1/messages", headers=self.auth_headers(config), json=payload
            )
            if resp.status_code >= 400:
                raise error_from_response(resp, self.name)
            body = resp.json()
        except ProviderError:
            raise
        except Exception as exc:
            raise error_from_exception(exc, self.name) from exc
        finally:
            await self._aclose(client)
        return self._parse_message(body, options.model)

    async def stream(
        self,
        config: RuntimeConfig,
        messages: list[ChatMessage],
        options: GenerationOptions,
    ) -> AsyncIterator[str]:
        base = self.effective_base_url(config)
        system, chat = self._split_system(messages)
        payload: dict[str, Any] = {
            "model": options.model,
            "messages": chat,
            "max_tokens": options.max_tokens,
            "temperature": options.temperature,
            "stream": True,
        }
        if system:
            payload["system"] = system

        client = self._get_client(config)
        try:
            async with client.stream(
                "POST",
                f"{base}/v1/messages",
                headers=self.auth_headers(config),
                json=payload,
            ) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    err_resp = httpx.Response(
                        status_code=resp.status_code,
                        content=body,
                        request=resp.request,
                    )
                    raise error_from_response(err_resp, self.name)
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta") or {}
                        if delta.get("type") == "text_delta":
                            text = delta.get("text")
                            if isinstance(text, str) and text:
                                yield text
                    elif event.get("type") == "error":
                        err = event.get("error") or {}
                        raise ProviderError(
                            "provider_error",
                            f"{self.name}: stream error — {err.get('message', 'unknown')}",
                            provider=self.name,
                        )
        except ProviderError:
            raise
        except Exception as exc:
            raise error_from_exception(exc, self.name) from exc
        finally:
            await self._aclose(client)

    def _parse_message(self, body: dict[str, Any], requested_model: str) -> ProviderResponse:
        content = body.get("content")
        if not isinstance(content, list) or not content:
            raise ProviderError(
                "malformed_response",
                f"{self.name}: response contained no content.",
                provider=self.name,
            )
        text_parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        text = "".join(text_parts)
        if not text.strip():
            stop = body.get("stop_reason")
            if stop == "max_tokens":
                raise ProviderError(
                    "response_truncated",
                    "The model response was cut off before completing. "
                    "Try a simpler request or a larger max_tokens setting.",
                    provider=self.name,
                )
            raise ProviderError(
                "malformed_response",
                f"{self.name}: response contained no text content.",
                provider=self.name,
            )
        usage = None
        raw_usage = body.get("usage")
        if isinstance(raw_usage, dict):
            usage = UsageInfo(
                prompt_tokens=raw_usage.get("input_tokens"),
                completion_tokens=raw_usage.get("output_tokens"),
            )
        return ProviderResponse(
            text=text,
            model=str(body.get("model") or requested_model),
            usage=usage,
            finish_reason=body.get("stop_reason"),
        )
