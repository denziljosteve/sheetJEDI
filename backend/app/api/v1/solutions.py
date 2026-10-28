"""Solution generation, streaming, and validation endpoints."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.errors import AppError, error_body
from app.db.session import get_db
from app.providers.base import ChatMessage, GenerationOptions
from app.providers.errors import ProviderError
from app.providers.registry import get_registry
from app.schemas.api import GenerationRequest, GenerationResponse
from app.schemas.solution import ValidationReport
from app.services import generation, safety, settings_service, solution_parser
from app.services.prompts import build_prompts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/solutions", tags=["solutions"])


@router.post("/generate", response_model=GenerationResponse)
async def generate_solution(
    request: GenerationRequest, db: Session = Depends(get_db)
) -> GenerationResponse:
    """Generate a structured spreadsheet solution from a natural-language request."""
    return await generation.generate_solution(db, request)


@router.post("/validate", response_model=ValidationReport)
async def validate_solution_payload(request: dict) -> ValidationReport:
    """Validate a raw solution JSON payload against the structured schema.

    This performs real schema/cross-field validation (it does not call any AI
    provider).
    """
    if not isinstance(request, dict):
        raise AppError("invalid_request", "Request body must be a JSON object.", status_code=422)
    report = solution_parser.validate_solution_payload(request)
    return report


async def _sse(event: str, data: dict) -> str:
    return f"data: {json.dumps({'event': event, **data}, ensure_ascii=False)}\n\n"


@router.post("/generate/stream")
async def generate_solution_stream(
    request: GenerationRequest, db: Session = Depends(get_db)
) -> StreamingResponse:
    """Stream token deltas from the primary provider, then the final solution.

    Differences from POST /solutions/generate:
    - Fallback providers and the validation-repair round-trip are NOT applied;
      on failure an ``error`` event is emitted instead.
    - The final ``done`` event contains the same validated solution object as
      the non-streaming endpoint (or a degraded one, flagged accordingly).
    """

    async def event_stream():
        registry = get_registry()
        try:
            app_settings = settings_service.get_app_settings(db)
            provider = request.provider or app_settings.default_provider
            if not provider:
                raise AppError(
                    "provider_not_configured",
                    "No AI provider is selected. Configure one in Settings first.",
                    status_code=400,
                )
            adapter = registry.get(provider)
            if adapter is None:
                raise AppError(
                    "unknown_provider", f"Unknown provider '{provider}'.", status_code=404
                )
            runtime = settings_service.resolve_runtime(db, provider)
            if not runtime.api_key and adapter.name != "omniroute":
                raise AppError(
                    "auth_error",
                    f"{adapter.display_name} has no API key configured.",
                    status_code=400,
                )
            model = request.model
            if not model:
                row = settings_service.get_provider_row(db, provider)
                model = row.default_model if row and row.default_model else None
            if not model:
                raise AppError(
                    "model_not_configured",
                    f"Select a model for {adapter.display_name} in settings.",
                    status_code=400,
                )

            system_prompt, user_prompt = build_prompts(request)
            options = GenerationOptions(
                model=model,
                temperature=0.2,
                max_tokens=4096,
                json_mode=adapter.capabilities.json_mode,
            )
            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt),
            ]

            yield await _sse("start", {"provider": provider, "model": model})
            chunks: list[str] = []
            async for delta in adapter.stream(runtime, messages, options):
                chunks.append(delta)
                yield await _sse("delta", {"text": delta})

            raw_text = "".join(chunks)
            report = solution_parser.validate_raw_output(raw_text)
            degraded = False
            if report.valid and report.solution is not None:
                solution = report.solution
            else:
                solution = solution_parser.build_degraded_solution(raw_text, request)
                degraded = True
            safety_warnings = safety.scan_artifact(
                solution.formula, solution.code, solution.code_language
            )
            if safety_warnings:
                solution.warnings = list(dict.fromkeys([*solution.warnings, *safety_warnings]))
            yield await _sse(
                "done",
                {
                    "solution": solution.model_dump(),
                    "provider": provider,
                    "model": model,
                    "degraded": degraded,
                },
            )
        except AppError as exc:
            yield await _sse("error", {"error": error_body(exc.code, exc.message)["error"]})
        except ProviderError as exc:
            yield await _sse("error", {"error": exc.to_dict()})
        except Exception:
            logger.exception("Streaming generation failed")
            yield await _sse(
                "error",
                {"error": error_body("internal_error", "Streaming failed unexpectedly.")["error"]},
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
