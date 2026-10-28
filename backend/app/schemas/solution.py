"""Structured solution schema — the core output contract of sheetJEDI.

The AI model is instructed to return JSON matching this shape. Responses are
validated and normalized before being returned to the client; a response that
fails validation triggers one repair attempt, then a graceful degraded result
(marked with warnings) rather than a silent failure.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Platform = Literal["excel", "google_sheets"]
TaskType = Literal[
    "formula",
    "vba_macro",
    "office_script",
    "apps_script",
    "data_cleaning",
    "data_analysis",
    "reporting",
    "charts",
    "troubleshooting",
    "other",
]
SkillLevel = Literal["beginner", "intermediate", "advanced"]

_MAX_TEXT = 20000


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    # Strip control characters except newlines/tabs.
    cleaned = "".join(ch for ch in value if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    cleaned = cleaned.strip()
    return cleaned[:_MAX_TEXT] if cleaned else None


class ImplementationStep(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    instructions: str = Field(min_length=1, max_length=_MAX_TEXT)
    cell_references: list[str] = Field(default_factory=list, max_length=50)
    code_location: str | None = None

    @field_validator("title", "instructions", mode="after")
    @classmethod
    def _strip_text(cls, v: str) -> str:
        return v.strip()

    @field_validator("code_location", mode="after")
    @classmethod
    def _clean_code_location(cls, v: str | None) -> str | None:
        return _clean(v)


class AlternativeSolution(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=_MAX_TEXT)
    formula: str | None = None
    code: str | None = None
    when_to_use: str | None = None

    @field_validator("formula", "code", "when_to_use", mode="after")
    @classmethod
    def _clean_optionals(cls, v: str | None) -> str | None:
        return _clean(v)


class CommonError(BaseModel):
    error: str = Field(min_length=1, max_length=300)
    cause: str = Field(min_length=1, max_length=2000)
    solution: str = Field(min_length=1, max_length=4000)


class SolutionResponse(BaseModel):
    """A complete, copy-ready spreadsheet solution."""

    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=_MAX_TEXT)
    platform: Platform
    task_type: TaskType
    task_category: str | None = Field(default=None, max_length=120)

    formula: str | None = None
    code: str | None = None
    code_language: str | None = Field(
        default=None,
        description="vba | office_script | apps_script — required when code is present",
    )
    required_version: str | None = Field(default=None, max_length=200)

    assumptions: list[str] = Field(default_factory=list, max_length=30)
    prerequisites: list[str] = Field(default_factory=list, max_length=30)
    explanation: str = Field(min_length=1, max_length=_MAX_TEXT)
    implementation_steps: list[ImplementationStep] = Field(default_factory=list, max_length=40)
    example_input: str | None = None
    expected_output: str | None = None

    alternative_solutions: list[AlternativeSolution] = Field(default_factory=list, max_length=10)
    common_errors: list[CommonError] = Field(default_factory=list, max_length=20)
    troubleshooting: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    confidence_notes: str | None = Field(default=None, max_length=_MAX_TEXT)

    @field_validator(
        "summary",
        "explanation",
        mode="after",
    )
    @classmethod
    def _strip(cls, v: str) -> str:
        cleaned = "".join(ch for ch in v if ch == "\n" or ch == "\t" or ord(ch) >= 32)
        return cleaned.strip() or v.strip()

    @field_validator(
        "formula",
        "code",
        "code_language",
        "required_version",
        "example_input",
        "expected_output",
        "confidence_notes",
        mode="after",
    )
    @classmethod
    def _clean_optionals(cls, v: str | None) -> str | None:
        return _clean(v)

    @field_validator(
        "assumptions",
        "prerequisites",
        "troubleshooting",
        "warnings",
        mode="after",
    )
    @classmethod
    def _clean_string_lists(cls, values: list[str]) -> list[str]:
        out: list[str] = []
        for v in values:
            c = _clean(v)
            if c:
                out.append(c)
        return out

    @model_validator(mode="after")
    def _cross_field_rules(self) -> SolutionResponse:
        if self.code and not self.code_language:
            raise ValueError("code_language is required when code is provided")
        if self.task_type == "formula" and not self.formula and not self.code:
            raise ValueError("formula solutions must include a formula")
        if self.code_language:
            self.code_language = self.code_language.lower().replace(" ", "_")
        # Never keep both empty primary outputs.
        if not self.formula and not self.code:
            raise ValueError("solution must include a formula or code")
        return self


class ValidationReport(BaseModel):
    """Result of validating a raw model response against the solution schema."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    solution: SolutionResponse | None = None
    degraded: bool = Field(
        default=False,
        description="True when the raw output could not be fully validated "
        "and was wrapped in a degraded response.",
    )
    raw_text: str | None = None


class RawModelOutput(BaseModel):
    """Internal transport for parsed-but-unvalidated model output."""

    text: str
    parsed: dict[str, Any] | None = None
    parse_error: str | None = None
