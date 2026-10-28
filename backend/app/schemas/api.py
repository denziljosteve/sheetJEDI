"""API request/response schemas for providers, generation, files, and history."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.solution import (
    Platform,
    SkillLevel,
    SolutionResponse,
    TaskType,
)

# ---------------------------------------------------------------------------
# Providers & settings
# ---------------------------------------------------------------------------


class ProviderStatus(BaseModel):
    name: str
    display_name: str
    protocol: str
    default_base_url: str
    capabilities: dict[str, bool]
    status_note: str | None = None
    verification_status: str
    docs_url: str | None = None
    # Configuration state — never includes the key itself.
    config_status: Literal["unconfigured", "configured", "tested", "failed"] = "unconfigured"
    api_key_hint: str | None = None
    base_url_override: str | None = None
    default_model: str | None = None
    timeout_seconds: float | None = None
    last_tested_at: datetime | None = None
    last_test_message: str | None = None


class ProviderConfigUpdate(BaseModel):
    api_key: str | None = Field(
        default=None,
        max_length=500,
        description="New API key; omit to keep the existing one.",
    )
    clear_api_key: bool = False
    base_url: str | None = Field(default=None, max_length=512)
    default_model: str | None = Field(default=None, max_length=256)
    timeout_seconds: float | None = Field(default=None, ge=5, le=600)

    @field_validator("base_url")
    @classmethod
    def _valid_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if not v.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return v.rstrip("/")

    @field_validator("api_key")
    @classmethod
    def _strip_key(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class ProviderTestResult(BaseModel):
    provider: str
    ok: bool
    message: str
    models_count: int | None = None
    latency_ms: int | None = None
    tested_at: datetime


class ModelListResponse(BaseModel):
    provider: str
    models: list[dict[str, Any]]
    source: Literal["live", "cache"] = "live"
    fetched_at: datetime | None = None


class AppSettings(BaseModel):
    """User-level defaults (not secrets)."""

    default_provider: str | None = None
    default_model: str | None = None
    fallback_provider: str | None = None
    fallback_model: str | None = None
    history_enabled: bool = True
    default_platform: Platform = "excel"
    default_skill_level: SkillLevel = "beginner"
    default_explanation_language: str = "English"


class AppSettingsUpdate(BaseModel):
    default_provider: str | None = None
    default_model: str | None = None
    fallback_provider: str | None = None
    fallback_model: str | None = None
    history_enabled: bool | None = None
    default_platform: Platform | None = None
    default_skill_level: SkillLevel | None = None
    default_explanation_language: str | None = Field(default=None, max_length=30)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


class SpreadsheetContext(BaseModel):
    """Optional context the user provides to sharpen the solution."""

    worksheet_names: str | None = Field(default=None, max_length=2000)
    column_names: str | None = Field(default=None, max_length=4000)
    input_data_description: str | None = Field(default=None, max_length=4000)
    expected_result: str | None = Field(default=None, max_length=4000)
    constraints: str | None = Field(default=None, max_length=4000)
    existing_formula_or_code: str | None = Field(default=None, max_length=8000)
    error_message: str | None = Field(default=None, max_length=2000)
    sample_data: str | None = Field(
        default=None,
        max_length=8000,
        description="Paste small sample data (e.g. CSV) to ground the solution.",
    )
    extra_notes: str | None = Field(default=None, max_length=4000)


class GenerationRequest(BaseModel):
    request: str = Field(min_length=3, max_length=6000)
    platform: Platform = "excel"
    task_type: TaskType = "formula"
    task_category: str | None = Field(default=None, max_length=120)
    excel_version: str | None = Field(default=None, max_length=60)
    sheets_version: str | None = Field(default=None, max_length=60)
    skill_level: SkillLevel = "beginner"
    explanation_language: str = Field(default="English", max_length=30)
    context: SpreadsheetContext = Field(default_factory=SpreadsheetContext)
    guided: dict[str, str] = Field(
        default_factory=dict,
        description="Dynamic guided inputs (lookup column, condition, etc.).",
    )
    provider: str | None = Field(default=None, max_length=50)
    model: str | None = Field(default=None, max_length=256)
    use_fallback: bool = True
    file_id: str | None = Field(default=None, max_length=64)
    include_file_context: bool = Field(
        default=False,
        description="Explicit consent to send extracted workbook context to the AI provider.",
    )

    @field_validator("guided")
    @classmethod
    def _bounded_guided(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) > 40:
            raise ValueError("too many guided inputs")
        out: dict[str, str] = {}
        for key, value in list(v.items())[:40]:
            k = str(key)[:80].strip()
            val = str(value)[:2000].strip()
            if k and val:
                out[k] = val
        return out


class UsageSummary(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class GenerationResponse(BaseModel):
    solution: SolutionResponse
    solution_id: str | None = None
    provider: str
    model: str
    fallback_used: bool = False
    degraded: bool = False
    degraded_notice: str | None = None
    usage: UsageSummary | None = None
    generated_at: datetime


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------


class ColumnProfile(BaseModel):
    name: str
    inferred_type: Literal["number", "date", "text", "boolean", "mixed", "empty"] = "text"
    non_empty: int = 0
    empty: int = 0
    distinct_sampled: int = 0
    sample_values: list[str] = Field(default_factory=list, max_length=5)


class SheetProfile(BaseModel):
    name: str
    total_rows_estimate: int | None = None
    total_columns: int = 0
    scanned_rows: int = 0
    truncated: bool = False
    headers: list[str] = Field(default_factory=list)
    columns: list[ColumnProfile] = Field(default_factory=list)
    sample_rows: list[list[str | None]] = Field(default_factory=list)
    duplicate_rows_scanned: int = 0


class AnalysisRecommendation(BaseModel):
    area: str
    recommendation: str


class WorkbookAnalysis(BaseModel):
    file_id: str
    filename: str
    file_type: str
    size_bytes: int
    sheet_count: int
    sheets: list[SheetProfile]
    recommendations: list[AnalysisRecommendation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    analyzed_at: datetime


class FileMetaOut(BaseModel):
    file_id: str
    filename: str
    file_type: str
    size_bytes: int
    status: str
    created_at: datetime
    expires_at: datetime | None = None


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


class HistoryItem(BaseModel):
    id: str
    platform: str
    task_type: str
    task_category: str | None = None
    skill_level: str | None = None
    title: str | None = None
    provider: str | None = None
    model: str | None = None
    fallback_used: bool = False
    created_at: datetime
    request_preview: str | None = None


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    total: int
    limit: int
    offset: int


class SolutionDetail(BaseModel):
    id: str
    platform: str
    task_type: str
    created_at: datetime
    request: dict[str, Any]
    solution: SolutionResponse
    provider: str | None = None
    model: str | None = None
    fallback_used: bool = False


class ValidateSolutionRequest(BaseModel):
    """Validate a raw solution JSON payload against the structured schema."""

    payload: dict[str, Any]
