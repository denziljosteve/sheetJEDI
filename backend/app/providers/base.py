"""Provider-independent interface shared by all AI adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class ProviderCapabilities:
    streaming: bool = True
    model_discovery: bool = True
    json_mode: bool = False  # native {"type": "json_object"} response_format support
    custom_base_url: bool = False
    configurable_timeout: bool = True


@dataclass
class ModelInfo:
    id: str
    name: str
    context_window: int | None = None
    capabilities: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "context_window": self.context_window,
            "capabilities": self.capabilities,
        }


@dataclass
class RuntimeConfig:
    """Resolved, decrypted runtime settings for one provider."""

    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: float = 60.0


@dataclass
class UsageInfo:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass
class ProviderResponse:
    text: str
    model: str
    usage: UsageInfo | None = None
    finish_reason: str | None = None


@dataclass
class TestResult:
    ok: bool
    message: str
    models_count: int | None = None
    latency_ms: int | None = None


@dataclass
class GenerationOptions:
    model: str
    temperature: float = 0.2
    max_tokens: int = 4096
    json_mode: bool = False


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


class ProviderAdapter(ABC):
    """Common interface every provider adapter implements."""

    name: str = "base"
    display_name: str = "Base"
    protocol: str = "unknown"
    default_base_url: str = ""
    capabilities: ProviderCapabilities = ProviderCapabilities()
    status_note: str | None = None
    verification_status: str = "untested"  # verified | untested | blocked
    docs_url: str | None = None

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    # -- configuration ------------------------------------------------------
    def effective_base_url(self, config: RuntimeConfig) -> str:
        base = (config.base_url or self.default_base_url).rstrip("/")
        return base

    def validate_config(self, config: RuntimeConfig) -> list[str]:
        """Return a list of configuration problems (empty when valid)."""
        problems: list[str] = []
        if not config.api_key:
            problems.append("API key is not configured.")
        if self.capabilities.custom_base_url is False and config.base_url:
            base = config.base_url.rstrip("/")
            if base != self.default_base_url.rstrip("/"):
                problems.append(f"Custom base URLs are not supported for {self.display_name}.")
        if self.capabilities.custom_base_url and not (config.base_url or self.default_base_url):
            problems.append("A base URL is required for this provider.")
        return problems

    # -- HTTP ---------------------------------------------------------------
    def _get_client(self, config: RuntimeConfig) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=config.timeout_seconds)

    async def _aclose(self, client: httpx.AsyncClient) -> None:
        if self._client is None:
            await client.aclose()

    @abstractmethod
    def auth_headers(self, config: RuntimeConfig) -> dict[str, str]: ...

    # -- operations ---------------------------------------------------------
    @abstractmethod
    async def list_models(self, config: RuntimeConfig) -> list[ModelInfo]: ...

    async def test_connection(self, config: RuntimeConfig) -> TestResult:
        import time

        problems = self.validate_config(config)
        if problems:
            return TestResult(ok=False, message=" ".join(problems))
        start = time.monotonic()
        try:
            models = await self.list_models(config)
        except Exception as exc:  # ProviderError or transport error
            from app.providers.errors import ProviderError, error_from_exception

            err = exc if isinstance(exc, ProviderError) else error_from_exception(exc, self.name)
            return TestResult(ok=False, message=err.message)
        latency = int((time.monotonic() - start) * 1000)
        return TestResult(
            ok=True,
            message=f"Connection successful. {len(models)} model(s) available.",
            models_count=len(models),
            latency_ms=latency,
        )

    @abstractmethod
    async def generate(
        self,
        config: RuntimeConfig,
        messages: list[ChatMessage],
        options: GenerationOptions,
    ) -> ProviderResponse: ...

    @abstractmethod
    def stream(
        self,
        config: RuntimeConfig,
        messages: list[ChatMessage],
        options: GenerationOptions,
    ) -> AsyncIterator[str]:
        """Yield text deltas as they arrive from the provider."""
        ...

    # -- metadata -----------------------------------------------------------
    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "protocol": self.protocol,
            "default_base_url": self.default_base_url,
            "capabilities": {
                "streaming": self.capabilities.streaming,
                "model_discovery": self.capabilities.model_discovery,
                "json_mode": self.capabilities.json_mode,
                "custom_base_url": self.capabilities.custom_base_url,
            },
            "status_note": self.status_note,
            "verification_status": self.verification_status,
            "docs_url": self.docs_url,
        }
