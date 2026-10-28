"""Provider error normalization.

All provider/network failures are converted into :class:`ProviderError` with a
stable machine-readable ``code``, a user-safe message, and a ``retryable``
flag. Bounded retries are only ever attempted for transient failures.
"""

from __future__ import annotations

import json
from typing import Any

import httpx


class ProviderError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
        provider: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status_code = status_code
        self.provider = provider
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.provider:
            d["provider"] = self.provider
        if self.status_code:
            d["status_code"] = self.status_code
        if self.details:
            d["details"] = self.details
        return d


def _extract_provider_message(response: httpx.Response) -> str:
    """Best-effort extraction of the provider's own error message."""
    try:
        body: Any = response.json()
    except (json.JSONDecodeError, ValueError):
        return response.text[:300] if response.text else ""
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and isinstance(err.get("message"), str):
            return err["message"][:500]
        if isinstance(err, str):
            return err[:500]
        if isinstance(body.get("message"), str):
            return body["message"][:500]
    return ""


def error_from_response(response: httpx.Response, provider: str) -> ProviderError:
    """Map an HTTP error response from any provider to a normalized error."""
    status = response.status_code
    upstream = _extract_provider_message(response) or f"HTTP {status}"

    if status in (401,):
        return ProviderError(
            "auth_error",
            f"{provider}: authentication failed. Check the API key in provider settings.",
            retryable=False,
            status_code=status,
            provider=provider,
        )
    if status == 403:
        return ProviderError(
            "permission_error",
            f"{provider}: access denied — {upstream}",
            retryable=False,
            status_code=status,
            provider=provider,
        )
    if status == 404:
        return ProviderError(
            "not_found",
            f"{provider}: endpoint or model not found — {upstream}",
            retryable=False,
            status_code=status,
            provider=provider,
        )
    if status == 408 or status == 504:
        return ProviderError(
            "timeout",
            f"{provider}: the request timed out upstream.",
            retryable=True,
            status_code=status,
            provider=provider,
        )
    if status == 429:
        retry_after = response.headers.get("retry-after")
        return ProviderError(
            "rate_limited",
            f"{provider}: rate limit or quota exceeded — {upstream}",
            retryable=True,
            status_code=status,
            provider=provider,
            details={"retry_after": retry_after} if retry_after else None,
        )
    if status == 422 or status == 400:
        return ProviderError(
            "invalid_request",
            f"{provider}: request rejected — {upstream}",
            retryable=False,
            status_code=status,
            provider=provider,
        )
    if status >= 500:
        return ProviderError(
            "provider_error",
            f"{provider}: service error (HTTP {status}).",
            retryable=True,
            status_code=status,
            provider=provider,
        )
    return ProviderError(
        "provider_error",
        f"{provider}: unexpected response — {upstream}",
        retryable=False,
        status_code=status,
        provider=provider,
    )


def error_from_exception(exc: Exception, provider: str) -> ProviderError:
    """Map network-level exceptions to normalized errors."""
    if isinstance(exc, httpx.TimeoutException):
        return ProviderError(
            "timeout",
            f"{provider}: request timed out. Try again or increase the timeout.",
            retryable=True,
            provider=provider,
        )
    if isinstance(exc, httpx.ConnectError | httpx.ConnectTimeout | httpx.NetworkError):
        return ProviderError(
            "connection_error",
            f"{provider}: could not reach the service. Check your network / base URL.",
            retryable=True,
            provider=provider,
        )
    if isinstance(exc, httpx.HTTPStatusError):
        return error_from_response(exc.response, provider)
    return ProviderError(
        "provider_error",
        f"{provider}: unexpected error ({type(exc).__name__}).",
        retryable=False,
        provider=provider,
    )
