"""ORM models.

Single-user, local-first data model:

- ``provider_configs``: one row per AI provider with an encrypted credential.
- ``solutions``: generated solution history (disabled via settings when the
  user opts out).
- ``files``: metadata + analysis JSON for uploaded workbooks. Uploaded file
  content itself is deleted immediately after analysis; only the structured
  analysis result is retained until expiry.
- ``app_settings``: small key/value JSON store (defaults, toggles).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class ProviderConfig(Base):
    __tablename__ = "provider_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_hint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    default_model: Mapped[str | None] = mapped_column(String(256), nullable=True)
    timeout_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    # unconfigured | configured | tested | failed
    status: Mapped[str] = mapped_column(String(20), default="unconfigured")
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Solution(Base):
    __tablename__ = "solutions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    platform: Mapped[str] = mapped_column(String(20))
    task_type: Mapped[str] = mapped_column(String(40))
    task_category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    skill_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    explanation_language: Mapped[str | None] = mapped_column(String(30), nullable=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    request_json: Mapped[str] = mapped_column(Text)
    response_json: Mapped[str] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(256), nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class FileMeta(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    original_name: Mapped[str] = mapped_column(String(255))
    safe_name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(10))
    size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="analyzed")
    analysis_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
