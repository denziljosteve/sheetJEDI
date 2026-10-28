"""Solution generation orchestration.

Lifecycle: validate request -> resolve provider -> build task-specific prompts
-> call provider (bounded retries for transient errors only) -> validate &
normalize structured output (with one repair round-trip) -> safety scan ->
persist history (per privacy settings) -> return typed response.

Fallback to a secondary provider is optional, explicit, and always surfaced to
the user — never silent.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.models import Solution
from app.providers.base import (
    ChatMessage,
    GenerationOptions,
    ProviderAdapter,
    ProviderResponse,
    RuntimeConfig,
)
from app.providers.errors import ProviderError
from app.providers.registry import get_registry
from app.schemas.api import GenerationRequest, GenerationResponse, UsageSummary
from app.schemas.solution import SolutionResponse
from app.services import prompts, safety, settings_service, solution_parser

logger = logging.getLogger(__name__)

_MAX_TRANSIENT_RETRIES = 2  # total attempts per provider (1 initial + 1 retry)
_RETRY_DELAYS = (1.0, 2.0)  # seconds, applied between attempts


async def _call_with_bounded_retries(
    coro_factory,
    *,
    delays: tuple[float, ...] = _RETRY_DELAYS,
) -> ProviderResponse:
    """Attempt a provider call; retry only on transient (retryable) errors."""
    last: ProviderError | None = None
    attempts = _MAX_TRANSIENT_RETRIES
    for attempt in range(attempts):
        try:
            return await coro_factory()
        except ProviderError as exc:
            if not exc.retryable or attempt == attempts - 1:
                raise
            last = exc
            delay = delays[min(attempt, len(delays) - 1)] if delays else 0.0
            logger.warning("Transient provider error (%s); retrying in %.1fs", exc.code, delay)
            await asyncio.sleep(delay)
    raise last if last else RuntimeError("unreachable")


def _version_line(req: GenerationRequest) -> str:
    if req.platform == "excel":
        return f"Excel ({req.excel_version or 'version unknown'})"
    return f"Google Sheets ({req.sheets_version or 'current'})"


def _build_file_context(req: GenerationRequest, analysis_json: str) -> str:
    """Compact, minimal workbook context for the prompt (consent already given)."""
    try:
        analysis = json.loads(analysis_json)
    except json.JSONDecodeError:
        return ""
    lines: list[str] = []
    for sheet in analysis.get("sheets", [])[:10]:
        headers = ", ".join(sheet.get("headers", [])[:30])
        lines.append(f"- Sheet '{sheet.get('name')}': columns [{headers}]")
        samples = sheet.get("sample_rows", [])[:2]
        for row in samples:
            preview = ", ".join(str(v)[:40] for v in row[:10])
            lines.append(f"    sample: {preview}")
    return "\n".join(lines)


def _resolve_provider_chain(
    db: Session,
    req: GenerationRequest,
) -> list[tuple[str, RuntimeConfig, str]]:
    """Return an ordered [(provider, runtime, reason)] chain: primary then fallback."""
    app_settings = settings_service.get_app_settings(db)
    registry = get_registry()

    primary = req.provider or app_settings.default_provider
    if not primary:
        raise AppError(
            "provider_not_configured",
            "No AI provider is selected. Configure one in Settings -> AI Providers first.",
            status_code=400,
        )
    if primary not in registry:
        raise AppError("unknown_provider", f"Unknown provider '{primary}'.", status_code=404)

    chain: list[tuple[str, RuntimeConfig, str]] = [
        (primary, settings_service.resolve_runtime(db, primary), "primary")
    ]

    fallback_provider = app_settings.fallback_provider
    if (
        req.use_fallback
        and fallback_provider
        and fallback_provider != primary
        and fallback_provider in registry
    ):
        fallback_runtime = settings_service.resolve_runtime(db, fallback_provider)
        has_key = bool(fallback_runtime.api_key)
        custom_url_ok = registry[fallback_provider].capabilities.custom_base_url
        if has_key or custom_url_ok:
            chain.append((fallback_provider, fallback_runtime, "fallback"))

    # Per-request model override applies to the primary provider.
    return chain


async def _generate_with_adapter(
    adapter: ProviderAdapter,
    runtime: RuntimeConfig,
    model: str,
    system_prompt: str,
    user_prompt: str,
    settings: Settings,
    *,
    max_tokens: int = 4096,
    delays: tuple[float, ...] = _RETRY_DELAYS,
) -> ProviderResponse:
    options = GenerationOptions(
        model=model,
        temperature=0.2,
        max_tokens=max_tokens,
        json_mode=adapter.capabilities.json_mode,
    )
    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]
    return await _call_with_bounded_retries(
        lambda: adapter.generate(runtime, messages, options), delays=delays
    )


async def _repair_with_adapter(
    adapter: ProviderAdapter,
    runtime: RuntimeConfig,
    model: str,
    system_prompt: str,
    user_prompt: str,
    previous_text: str,
    errors: list[str],
    settings: Settings,
) -> ProviderResponse | None:
    """One repair round-trip: feed validation errors back to the model."""
    repair_user = (
        f"{user_prompt}\n\n---\nYour previous response failed validation with these errors:\n"
        + "\n".join(f"- {e}" for e in errors[:10])
        + "\n\nPrevious response (invalid):\n"
        + previous_text[:6000]
        + "\n\nReturn the corrected JSON object now, and nothing else."
    )
    try:
        return await _generate_with_adapter(
            adapter, runtime, model, system_prompt, repair_user, settings
        )
    except ProviderError as exc:
        logger.warning("Repair attempt failed for provider %s: %s", adapter.name, exc.code)
        return None


async def generate_solution(
    db: Session,
    req: GenerationRequest,
    *,
    settings: Settings | None = None,
    retry_delays: tuple[float, ...] = _RETRY_DELAYS,
) -> GenerationResponse:
    settings = settings or get_settings()
    registry = get_registry()

    # Optional file context (requires explicit consent).
    file_context = ""
    if req.file_id and req.include_file_context:
        from app.db.models import FileMeta

        meta = db.get(FileMeta, req.file_id)
        if meta is None:
            raise AppError("file_not_found", "Attached file analysis not found.", status_code=404)
        file_context = _build_file_context(req, meta.analysis_json or "")

    system_prompt, user_prompt = prompts.build_prompts(req)
    if file_context:
        user_prompt = user_prompt + "\n\n" + prompts.build_file_context_prompt(file_context)

    chain = _resolve_provider_chain(db, req)
    if not chain:
        raise AppError(
            "provider_not_configured",
            "No usable AI provider is configured. Add an API key in Settings.",
            status_code=400,
        )

    primary_provider = chain[0][0]
    last_error: ProviderError | None = None

    for provider_name, runtime, reason in chain:
        adapter = registry[provider_name]
        model = req.model if (req.model and reason == "primary") else None
        if model is None:
            row = settings_service.get_provider_row(db, provider_name)
            model = (row.default_model if row and row.default_model else None) or _default_model(
                adapter, db, provider_name
            )
        if not model:
            last_error = ProviderError(
                "model_not_configured",
                f"{adapter.display_name}: no model selected. Choose a model in settings "
                "or enter a model ID manually.",
                provider=provider_name,
            )
            continue
        if not runtime.api_key and adapter.name != "omniroute":
            last_error = ProviderError(
                "auth_error",
                f"{adapter.display_name}: no API key configured. Add one in "
                "Settings -> AI Providers.",
                provider=provider_name,
            )
            continue

        try:
            response = await _generate_with_adapter(
                adapter,
                runtime,
                model,
                system_prompt,
                user_prompt,
                settings,
                delays=retry_delays,
            )
        except ProviderError as exc:
            last_error = exc
            logger.warning("Generation failed on %s (%s): %s", provider_name, exc.code, exc.message)
            continue

        report = solution_parser.validate_raw_output(response.text)
        degraded = False
        degraded_notice: str | None = None

        if not report.valid:
            repair = await _repair_with_adapter(
                adapter,
                runtime,
                model,
                system_prompt,
                user_prompt,
                response.text,
                report.errors,
                settings,
            )
            if repair is not None:
                report = solution_parser.validate_raw_output(repair.text)
                if report.valid:
                    response = repair

        if not report.valid or report.solution is None:
            solution = solution_parser.build_degraded_solution(response.text, req)
            degraded = True
            degraded_notice = (
                "The model output could not be validated ("
                + "; ".join(report.errors[:3])
                + "). Raw output shown for manual review."
            )
        else:
            solution = report.solution

        # Safety scan (never executes generated content).
        safety_warnings = safety.scan_artifact(
            solution.formula, solution.code, solution.code_language
        )
        if safety_warnings:
            solution.warnings = list(dict.fromkeys([*solution.warnings, *safety_warnings]))

        fallback_used = reason == "fallback" or provider_name != primary_provider
        if fallback_used:
            solution.warnings = [
                f"Generated with fallback provider '{adapter.display_name}' because the "
                f"primary provider failed ({last_error.code if last_error else 'error'}). "
                "Results, cost, and data handling may differ from the primary provider.",
                *solution.warnings,
            ]

        solution_id = _persist_history(
            db, req, solution, provider_name, response.model, fallback_used, settings
        )

        usage = None
        if response.usage:
            usage = UsageSummary(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
            )

        return GenerationResponse(
            solution=solution,
            solution_id=solution_id,
            provider=provider_name,
            model=response.model,
            fallback_used=fallback_used,
            degraded=degraded,
            degraded_notice=degraded_notice,
            usage=usage,
            generated_at=datetime.now(UTC),
        )

    # All candidates failed.
    assert last_error is not None
    raise AppError(
        last_error.code,
        last_error.message,
        status_code=502,
        details={"provider": last_error.provider} if last_error.provider else None,
    )


def _default_model(adapter: ProviderAdapter, db: Session, provider: str) -> str | None:
    """Pick a sensible default model for the provider when none is configured."""
    app_settings = settings_service.get_app_settings(db)
    if app_settings.default_provider == provider and app_settings.default_model:
        return app_settings.default_model
    # No hard-coded "current" catalog: default models are intentionally not
    # baked in — the user picks from the live model list or enters an ID.
    return None


def _persist_history(
    db: Session,
    req: GenerationRequest,
    solution: SolutionResponse,
    provider: str,
    model: str,
    fallback_used: bool,
    settings: Settings,
) -> str | None:
    if not settings.history_enabled:
        return None
    app_settings = settings_service.get_app_settings(db)
    if not app_settings.history_enabled:
        return None
    # Store request metadata; do not store spreadsheet sample data contents.
    request_meta = req.model_dump(
        include={
            "platform",
            "task_type",
            "task_category",
            "skill_level",
            "explanation_language",
            "excel_version",
            "sheets_version",
        }
    )
    request_meta["request_text"] = req.request
    entry = Solution(
        platform=req.platform,
        task_type=req.task_type,
        task_category=req.task_category,
        skill_level=req.skill_level,
        explanation_language=req.explanation_language,
        title=solution.title,
        request_json=json.dumps(request_meta, ensure_ascii=False),
        response_json=solution.model_dump_json(),
        provider=provider,
        model=model,
        fallback_used=fallback_used,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry.id
