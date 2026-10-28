"""Logging setup with secret redaction.

Anything that looks like an API key (or any value registered at runtime) is
masked before the record is emitted, so credentials never reach log files.
"""

from __future__ import annotations

import logging
import re
import threading

_REDACTED = "***REDACTED***"

# Patterns that commonly match provider API keys / bearer tokens.
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),  # OpenAI-style
    re.compile(r"gsk_[A-Za-z0-9_\-]{8,}"),  # Groq-style
    re.compile(r"ak_[A-Za-z0-9_\-]{8,}"),  # LongCat-style
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"),
    re.compile(r'(?i)("(?:api[_-]?key|x-api-key|authorization)"\s*:\s*")[^"]+(")'),
]

_registered_secrets: set[str] = set()
_registry_lock = threading.Lock()


def register_secret(value: str) -> None:
    """Register an exact secret value so it is masked in all future log records."""
    if value and len(value) >= 8:
        with _registry_lock:
            _registered_secrets.add(value)


def redact(text: str) -> str:
    """Mask registered secrets and key-shaped substrings in ``text``."""
    if not text:
        return text
    with _registry_lock:
        secrets = list(_registered_secrets)
    for secret in secrets:
        if secret in text:
            text = text.replace(secret, _REDACTED)
    for pattern in _SECRET_PATTERNS[:-1]:
        text = pattern.sub(_REDACTED, text)
    # Handle the JSON-shaped pattern with capture groups separately.
    text = _SECRET_PATTERNS[-1].sub(r"\1" + _REDACTED + r"\2", text)
    return text


class RedactingFilter(logging.Filter):
    """Logging filter that redacts secrets from the formatted message."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - defensive
            return True
        redacted = redact(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging with redaction. Safe to call multiple times."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
        handler.addFilter(RedactingFilter())
        root.addHandler(handler)
    # Ensure our filter also lands on handlers configured elsewhere (e.g. uvicorn).
    for existing in root.handlers:
        if not any(isinstance(f, RedactingFilter) for f in existing.filters):
            existing.addFilter(RedactingFilter())
