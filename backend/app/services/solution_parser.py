"""Parse and validate raw model output against the solution schema.

An LLM response is never trusted merely because it parses as JSON: it must also
satisfy cross-field validation (platform literals, code_language consistency,
formula/code presence). One repair round-trip is attempted on failure; after
that the raw output is surfaced in a clearly-marked degraded response instead
of being silently discarded or silently accepted.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from app.schemas.api import GenerationRequest
from app.schemas.solution import SolutionResponse, ValidationReport

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json_object(text: str) -> tuple[dict[str, Any] | None, str | None]:
    """Extract the first top-level JSON object from model output.

    Tolerates markdown fences and leading/trailing prose (common LLM behaviors).
    Returns (parsed, error).
    """
    if not text or not text.strip():
        return None, "empty response"

    candidate = text.strip()

    fenced = _FENCE_RE.findall(candidate)
    if fenced:
        candidate = fenced[0].strip()

    if not candidate.startswith("{"):
        start = candidate.find("{")
        if start == -1:
            return None, "no JSON object found in response"
        candidate = candidate[start:]

    if not candidate.endswith("}"):
        end = candidate.rfind("}")
        if end == -1:
            return None, "no closing JSON brace found"
        candidate = candidate[: end + 1]

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        # One retry heuristic: some models escape newlines inside strings poorly.
        return None, f"invalid JSON: {exc.msg} at position {exc.pos}"

    if not isinstance(parsed, dict):
        return None, "top-level JSON value is not an object"
    return parsed, None


def validate_solution_payload(payload: dict[str, Any]) -> ValidationReport:
    """Validate a parsed payload against the solution schema."""
    try:
        solution = SolutionResponse.model_validate(payload)
    except ValidationError as exc:
        errors = []
        for err in exc.errors()[:15]:
            loc = ".".join(str(p) for p in err.get("loc", []))
            errors.append(f"{loc}: {err.get('msg', 'invalid')}")
        return ValidationReport(valid=False, errors=errors)
    return ValidationReport(valid=True, solution=solution)


def validate_raw_output(text: str) -> ValidationReport:
    """Parse raw model text and validate it into a SolutionResponse."""
    payload, parse_error = extract_json_object(text)
    if payload is None:
        return ValidationReport(valid=False, errors=[parse_error or "unparseable output"])
    report = validate_solution_payload(payload)
    if not report.valid:
        report.raw_text = text
    return report


def build_degraded_solution(text: str, req: GenerationRequest) -> SolutionResponse:
    """Wrap unvalidated model output in a clearly-marked degraded solution.

    Used only after a repair attempt also failed. The raw text is preserved so
    the user can still copy something useful, but it is flagged prominently.
    """
    snippet = text.strip()
    first_line = snippet.splitlines()[0][:120] if snippet else "Unvalidated output"
    return SolutionResponse.model_construct(
        title=f"Unvalidated response — please review carefully ({first_line})",
        summary=(
            "The AI provider returned output that failed schema validation, and the "
            "automatic repair attempt also failed. The raw response is shown below "
            "exactly as received — treat it as unverified text, not a validated solution."
        ),
        platform=req.platform,
        task_type=req.task_type,
        task_category=req.task_category,
        formula=None,
        code=snippet[:20000],
        code_language="unvalidated_output",
        required_version=None,
        assumptions=[],
        prerequisites=[],
        explanation=snippet[:20000],
        implementation_steps=[],
        example_input=None,
        expected_output=None,
        alternative_solutions=[],
        common_errors=[],
        troubleshooting=[],
        warnings=[
            "This response could not be validated against the solution schema. "
            "Review every line before using it."
        ],
        confidence_notes=None,
    )
