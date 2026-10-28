"""Provider configuration and app-settings services.

Credentials are encrypted at rest (Fernet) and never returned to the client —
only a masked hint such as ``••••abcd``. Connection status reflects reality:
"tested" is set only after an actual successful connection test.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.logging import register_secret
from app.core.security import decrypt_secret, encrypt_secret, mask_key
from app.db.models import AppSetting, ProviderConfig
from app.providers.base import ProviderAdapter, RuntimeConfig
from app.providers.registry import get_registry
from app.schemas.api import AppSettings as AppSettingsSchema
from app.schemas.api import AppSettingsUpdate, ProviderConfigUpdate, ProviderStatus

APP_SETTINGS_KEY = "app"


def get_provider_row(db: Session, provider: str) -> ProviderConfig | None:
    return db.scalar(select(ProviderConfig).where(ProviderConfig.provider == provider))


def resolve_runtime(db: Session, provider: str, settings: Settings | None = None) -> RuntimeConfig:
    """Resolve decrypted runtime settings for a provider (server-side only)."""
    settings = settings or get_settings()
    registry = get_registry()
    adapter = registry.get(provider)
    if adapter is None:
        raise AppError("unknown_provider", f"Unknown provider '{provider}'.", status_code=404)
    row = get_provider_row(db, provider)
    api_key: str | None = None
    if row and row.api_key_encrypted:
        api_key = decrypt_secret(row.api_key_encrypted, settings)
        register_secret(api_key)
    timeout = (row.timeout_seconds if row and row.timeout_seconds else None) or (
        settings.provider_timeout_seconds
    )
    return RuntimeConfig(
        api_key=api_key,
        base_url=row.base_url if row else None,
        timeout_seconds=timeout,
    )


def upsert_provider_config(
    db: Session,
    provider: str,
    update: ProviderConfigUpdate,
    settings: Settings | None = None,
) -> ProviderConfig:
    settings = settings or get_settings()
    registry = get_registry()
    adapter = registry.get(provider)
    if adapter is None:
        raise AppError("unknown_provider", f"Unknown provider '{provider}'.", status_code=404)

    row = get_provider_row(db, provider)
    if row is None:
        row = ProviderConfig(provider=provider)
        db.add(row)

    if update.clear_api_key:
        row.api_key_encrypted = None
        row.api_key_hint = None
        row.status = "unconfigured"
        row.last_tested_at = None
        row.last_test_message = None
    elif update.api_key:
        row.api_key_encrypted = encrypt_secret(update.api_key, settings)
        row.api_key_hint = mask_key(update.api_key)
        register_secret(update.api_key)
        # A changed credential invalidates the previous test result.
        row.status = "configured"
        row.last_tested_at = None
        row.last_test_message = None

    if update.base_url is not None:
        if not adapter.capabilities.custom_base_url and update.base_url.rstrip("/") != (
            adapter.default_base_url.rstrip("/")
        ):
            raise AppError(
                "invalid_config",
                f"{adapter.display_name} does not support a custom base URL.",
                status_code=422,
            )
        row.base_url = update.base_url
    if update.default_model is not None:
        row.default_model = update.default_model or None
    if update.timeout_seconds is not None:
        row.timeout_seconds = update.timeout_seconds

    if row.api_key_encrypted and row.status == "unconfigured":
        row.status = "configured"
    db.commit()
    db.refresh(row)
    invalidate_model_cache(provider)
    return row


def provider_status(adapter: ProviderAdapter, row: ProviderConfig | None) -> ProviderStatus:
    config_status: str = "unconfigured"
    if row is not None and (row.api_key_encrypted or row.base_url):
        config_status = row.status if row.status != "unconfigured" else "configured"
    return ProviderStatus(
        name=adapter.name,
        display_name=adapter.display_name,
        protocol=adapter.protocol,
        default_base_url=adapter.default_base_url,
        capabilities={
            "streaming": adapter.capabilities.streaming,
            "model_discovery": adapter.capabilities.model_discovery,
            "json_mode": adapter.capabilities.json_mode,
            "custom_base_url": adapter.capabilities.custom_base_url,
        },
        status_note=adapter.status_note,
        verification_status=adapter.verification_status,
        docs_url=adapter.docs_url,
        config_status=config_status,  # type: ignore[arg-type]
        api_key_hint=row.api_key_hint if row else None,
        base_url_override=row.base_url if row else None,
        default_model=row.default_model if row else None,
        timeout_seconds=row.timeout_seconds if row else None,
        last_tested_at=row.last_tested_at if row else None,
        last_test_message=row.last_test_message if row else None,
    )


def mark_test_result(db: Session, provider: str, ok: bool, message: str) -> None:
    row = get_provider_row(db, provider)
    if row is None:
        row = ProviderConfig(provider=provider)
        db.add(row)
    row.last_tested_at = datetime.now(UTC)
    row.last_test_message = message[:1000]
    row.status = "tested" if ok else "failed"
    db.commit()


# ---------------------------------------------------------------------------
# App-level settings (non-secret defaults)
# ---------------------------------------------------------------------------


def _load_app_settings(db: Session) -> AppSettingsSchema:
    row = db.get(AppSetting, APP_SETTINGS_KEY)
    if row is None:
        return AppSettingsSchema(history_enabled=get_settings().history_enabled)
    try:
        return AppSettingsSchema.model_validate(json.loads(row.value_json))
    except Exception:
        return AppSettingsSchema(history_enabled=get_settings().history_enabled)


def get_app_settings(db: Session) -> AppSettingsSchema:
    return _load_app_settings(db)


def update_app_settings(db: Session, update: AppSettingsUpdate) -> AppSettingsSchema:
    current = _load_app_settings(db)
    data = current.model_dump()
    for key, value in update.model_dump(exclude_unset=True).items():
        if value is not None:
            data[key] = value
    new_settings = AppSettingsSchema.model_validate(data)
    row = db.get(AppSetting, APP_SETTINGS_KEY)
    if row is None:
        row = AppSetting(key=APP_SETTINGS_KEY, value_json=new_settings.model_dump_json())
        db.add(row)
    else:
        row.value_json = new_settings.model_dump_json()
    db.commit()
    return new_settings


def settings_dict(settings: AppSettingsSchema) -> dict[str, Any]:
    return settings.model_dump()


# ---------------------------------------------------------------------------
# Model list cache (in-process, TTL-based)
# ---------------------------------------------------------------------------

_model_cache: dict[str, tuple[datetime, list[dict[str, Any]]]] = {}


def invalidate_model_cache(provider: str | None = None) -> None:
    if provider is None:
        _model_cache.clear()
    else:
        _model_cache.pop(provider, None)


def get_cached_models(provider: str, ttl_seconds: int) -> list[dict[str, Any]] | None:
    entry = _model_cache.get(provider)
    if entry is None:
        return None
    fetched_at, models = entry
    age = (datetime.now(UTC) - fetched_at).total_seconds()
    if age > ttl_seconds:
        _model_cache.pop(provider, None)
        return None
    return models


def set_cached_models(provider: str, models: list[dict[str, Any]]) -> None:
    _model_cache[provider] = (datetime.now(UTC), models)
