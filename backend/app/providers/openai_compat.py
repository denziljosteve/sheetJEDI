"""Adapter for OpenAI-compatible chat-completion APIs.

Covers Groq, OpenRouter, OpenAI, and OmniRoute (a self-hosted gateway).
Each provider differs in authentication extras, JSON mode support, and base
URL policy, so those aspects are configured per provider rather than assumed.
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


class OpenAIChatAdapter(ProviderAdapter):
    protocol = "openai_chat"

    def __init__(
        self,
        *,
        name: str,
        display_name: str,
        default_base_url: str,
        custom_base_url: bool = False,
        json_mode: bool = True,
        extra_headers: dict[str, str] | None = None,
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
            json_mode=json_mode,
            custom_base_url=custom_base_url,
        )
        self._extra_headers = extra_headers or {}
        self.status_note = status_note
        self.verification_status = verification_status
        self.docs_url = docs_url

    def auth_headers(self, config: RuntimeConfig) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self._extra_headers}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        return headers

    async def list_models(self, config: RuntimeConfig) -> list[ModelInfo]:
        base = self.effective_base_url(config)
        client = self._get_client(config)
        try:
            resp = await client.get(f"{base}/models", headers=self.auth_headers(config))
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
            ctx = item.get("context_length")
            caps: dict[str, Any] = {}
            arch = item.get("architecture")
            if isinstance(arch, dict):
                caps["modality"] = arch.get("input_modalities")
            models.append(
                ModelInfo(
                    id=str(item["id"]),
                    name=str(item.get("name") or item["id"]),
                    context_window=ctx if isinstance(ctx, int) else None,
                    capabilities=caps,
                )
            )
        if not models:
            models = []
        return sorted(models, key=lambda m: m.id)

    async def generate(
        self,
        config: RuntimeConfig,
        messages: list[ChatMessage],
        options: GenerationOptions,
    ) -> ProviderResponse:
        base = self.effective_base_url(config)
        payload: dict[str, Any] = {
            "model": options.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": options.temperature,
            "max_tokens": options.max_tokens,
        }
        use_json_mode = options.json_mode and self.capabilities.json_mode
        if use_json_mode:
            payload["response_format"] = {"type": "json_object"}

        client = self._get_client(config)
        try:
            resp = await client.post(
                f"{base}/chat/completions", headers=self.auth_headers(config), json=payload
            )
            # Some gateways reject response_format; retry once without it.
            if resp.status_code == 400 and use_json_mode and "response_format" in resp.text:
                payload.pop("response_format", None)
                resp = await client.post(
                    f"{base}/chat/completions",
                    headers=self.auth_headers(config),
                    json=payload,
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

        return self._parse_completion(body, options.model)

    async def stream(
        self,
        config: RuntimeConfig,
        messages: list[ChatMessage],
        options: GenerationOptions,
    ) -> AsyncIterator[str]:
        base = self.effective_base_url(config)
        payload: dict[str, Any] = {
            "model": options.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": options.temperature,
            "max_tokens": options.max_tokens,
            "stream": True,
        }
        if options.json_mode and self.capabilities.json_mode:
            payload["response_format"] = {"type": "json_object"}

        client = self._get_client(config)
        try:
            async with client.stream(
                "POST",
                f"{base}/chat/completions",
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
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    if choices:
                        delta = choices[0].get("delta") or {}
                        content = delta.get("content")
                        if isinstance(content, str) and content:
                            yield content
        except ProviderError:
            raise
        except Exception as exc:
            raise error_from_exception(exc, self.name) from exc
        finally:
            await self._aclose(client)

    def _parse_completion(self, body: dict[str, Any], requested_model: str) -> ProviderResponse:
        choices = body.get("choices") or []
        if not choices:
            raise ProviderError(
                "malformed_response",
                f"{self.name}: response contained no choices.",
                provider=self.name,
            )
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            finish = choices[0].get("finish_reason")
            if finish == "length":
                raise ProviderError(
                    "response_truncated",
                    "The model response was cut off before completing. "
                    "Try a simpler request or a model with a larger output limit.",
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
                prompt_tokens=raw_usage.get("prompt_tokens"),
                completion_tokens=raw_usage.get("completion_tokens"),
            )
        return ProviderResponse(
            text=content,
            model=str(body.get("model") or requested_model),
            usage=usage,
            finish_reason=choices[0].get("finish_reason"),
        )
