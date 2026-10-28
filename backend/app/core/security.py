"""Encryption-at-rest helpers for stored provider API keys.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` package — an
established, audited mechanism — rather than a homemade scheme.

Master key resolution order:
1. ``SHEETJEDI_SECRET_KEY`` environment setting (required in production).
2. Development fallback: auto-generate and persist to ``data/.master_key``
   (git-ignored, file permissions as restrictive as the OS allows).
"""

from __future__ import annotations

import contextlib
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

_DATA_DIR = Path("data")
_KEY_FILE = _DATA_DIR / ".master_key"

_fernet: Fernet | None = None


def _load_or_create_fernet(settings: Settings) -> Fernet:
    key = settings.secret_key.strip()
    if key:
        try:
            return Fernet(key.encode("utf-8"))
        except Exception as exc:
            raise AppError(
                "config_error",
                "SHEETJEDI_SECRET_KEY is not a valid Fernet key. "
                'Generate one with: python -c "from cryptography.fernet import '
                'Fernet; print(Fernet.generate_key().decode())"',
                status_code=500,
            ) from exc

    if settings.is_production:
        raise AppError(
            "config_error",
            "SHEETJEDI_SECRET_KEY is required in production.",
            status_code=500,
        )

    # Development fallback: generate once, persist locally (git-ignored).
    if _KEY_FILE.exists():
        stored = _KEY_FILE.read_text(encoding="utf-8").strip()
        return Fernet(stored.encode("utf-8"))
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    new_key = Fernet.generate_key()
    _KEY_FILE.write_text(new_key.decode("utf-8"), encoding="utf-8")
    with contextlib.suppress(OSError):  # pragma: no cover - platform dependent
        os.chmod(_KEY_FILE, 0o600)
    logger.warning(
        "No SHEETJEDI_SECRET_KEY configured; generated a development key at %s. "
        "Set SHEETJEDI_SECRET_KEY for reproducible deployments.",
        _KEY_FILE,
    )
    return Fernet(new_key)


def get_fernet(settings: Settings) -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = _load_or_create_fernet(settings)
    return _fernet


def encrypt_secret(plaintext: str, settings: Settings) -> str:
    return get_fernet(settings).encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str, settings: Settings) -> str:
    try:
        return get_fernet(settings).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise AppError(
            "secret_decryption_failed",
            "Stored credential could not be decrypted. The master key may have "
            "changed; re-enter the API key in provider settings.",
            status_code=409,
        ) from exc


def mask_key(key: str) -> str:
    """Return a display-safe hint for a key, e.g. ``sk-...abcd`` -> ``••••abcd``."""
    if not key:
        return ""
    tail = key[-4:] if len(key) >= 4 else ""
    return f"••••{tail}" if tail else "••••"
