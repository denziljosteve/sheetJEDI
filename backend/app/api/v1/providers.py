"""Provider discovery, connection testing, and secure configuration."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.providers.base import ModelInfo
from app.providers.errors import ProviderError
from app.providers.registry import PROVIDER_ORDER, get_registry
from app.schemas.api import (
    AppSettings as AppSettingsSchema,
)
from app.schemas.api import (
    AppSettingsUpdate,
    ModelListResponse,
    ProviderConfigUpdate,
    ProviderStatus,
    ProviderTestResult,
)
from app.services import settings_service

router = APIRouter(tags=["providers"])


def _get_adapter(provider: str):
    adapter = get_registry().get(provider)
    if adapter is None:
        raise AppError("unknown_provider", f"Unknown provider '{provider}'.", status_code=404)
    return adapter


@router.get("/providers", response_model=list[ProviderStatus])
async def list_providers(db: Session = Depends(get_db)) -> list[ProviderStatus]:
    """All providers with configuration state (keys are never included)."""
    registry = get_registry()
    out: list[ProviderStatus] = []
    for name in PROVIDER_ORDER:
        adapter = registry[name]
        row = settings_service.get_provider_row(db, name)
        out.append(settings_service.provider_status(adapter, row))
    return out


@router.get("/settings/providers", response_model=list[ProviderStatus])
async def list_provider_settings(db: Session = Depends(get_db)) -> list[ProviderStatus]:
    """Alias of GET /providers for the settings UI."""
    return await list_providers(db)


@router.get("/providers/{provider}/models", response_model=ModelListResponse)
async def list_provider_models(
    provider: str,
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ModelListResponse:
    """Fetch available models dynamically (cached with a TTL).

    Falls back to a 4xx with an actionable message when the provider is not
    configured; never fabricates a model catalog.
    """
    adapter = _get_adapter(provider)
    settings = get_settings()
    if not refresh:
        cached = settings_service.get_cached_models(provider, settings.model_cache_ttl_seconds)
        if cached is not None:
            return ModelListResponse(
                provider=provider,
                models=cached,
                source="cache",
                fetched_at=datetime.now(UTC),
            )
    runtime = settings_service.resolve_runtime(db, provider)
    if not runtime.api_key and adapter.capabilities.custom_base_url is False:
        raise AppError(
            "provider_not_configured",
            f"{adapter.display_name} has no API key configured. Add one in settings first.",
            status_code=400,
        )
    try:
        models: list[ModelInfo] = await adapter.list_models(runtime)
    except ProviderError as exc:
        raise AppError(exc.code, exc.message, status_code=502) from exc
    payload = [m.to_dict() for m in models]
    settings_service.set_cached_models(provider, payload)
    return ModelListResponse(
        provider=provider, models=payload, source="live", fetched_at=datetime.now(UTC)
    )


@router.post("/providers/{provider}/test", response_model=ProviderTestResult)
async def test_provider(provider: str, db: Session = Depends(get_db)) -> ProviderTestResult:
    """Perform an actual connection test; the recorded status reflects its outcome."""
    adapter = _get_adapter(provider)
    runtime = settings_service.resolve_runtime(db, provider)
    result = await adapter.test_connection(runtime)
    settings_service.mark_test_result(db, provider, result.ok, result.message)
    return ProviderTestResult(
        provider=provider,
        ok=result.ok,
        message=result.message,
        models_count=result.models_count,
        latency_ms=result.latency_ms,
        tested_at=datetime.now(UTC),
    )


@router.put("/settings/providers/{provider}", response_model=ProviderStatus)
async def update_provider_config(
    provider: str,
    update: ProviderConfigUpdate,
    db: Session = Depends(get_db),
) -> ProviderStatus:
    """Create or update a provider configuration.

    The API key is stored encrypted at rest; responses only ever include a
    masked hint.
    """
    adapter = _get_adapter(provider)
    row = settings_service.upsert_provider_config(db, provider, update)
    return settings_service.provider_status(adapter, row)


@router.get("/settings/app", response_model=AppSettingsSchema)
async def get_app_settings(db: Session = Depends(get_db)) -> AppSettingsSchema:
    return settings_service.get_app_settings(db)


@router.put("/settings/app", response_model=AppSettingsSchema)
async def update_app_settings(
    update: AppSettingsUpdate, db: Session = Depends(get_db)
) -> AppSettingsSchema:
    return settings_service.update_app_settings(db, update)
