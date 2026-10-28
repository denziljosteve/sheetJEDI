"""Solution history persistence and queries (respecting the privacy toggle)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Solution
from app.schemas.api import HistoryItem, HistoryPage, SolutionDetail
from app.schemas.solution import SolutionResponse


def list_history(db: Session, limit: int = 20, offset: int = 0) -> HistoryPage:
    total = db.scalar(select(func.count(Solution.id))) or 0
    rows = db.scalars(
        select(Solution)
        .order_by(Solution.created_at.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    ).all()
    items: list[HistoryItem] = []
    for row in rows:
        try:
            request_meta = json.loads(row.request_json)
        except json.JSONDecodeError:
            request_meta = {}
        preview = str(request_meta.get("request_text", ""))[:120]
        items.append(
            HistoryItem(
                id=row.id,
                platform=row.platform,
                task_type=row.task_type,
                task_category=row.task_category,
                skill_level=row.skill_level,
                title=row.title,
                provider=row.provider,
                model=row.model,
                fallback_used=row.fallback_used,
                created_at=row.created_at,
                request_preview=preview,
            )
        )
    return HistoryPage(items=items, total=total, limit=limit, offset=offset)


def get_history_item(db: Session, solution_id: str) -> SolutionDetail:
    row = db.get(Solution, solution_id)
    if row is None:
        raise AppError("history_not_found", "Solution not found in history.", status_code=404)
    try:
        request_meta: dict[str, Any] = json.loads(row.request_json)
    except json.JSONDecodeError:
        request_meta = {}
    try:
        solution = SolutionResponse.model_validate(json.loads(row.response_json))
    except Exception as exc:
        raise AppError(
            "history_corrupt",
            "Stored solution could not be deserialized.",
            status_code=500,
        ) from exc
    return SolutionDetail(
        id=row.id,
        platform=row.platform,
        task_type=row.task_type,
        created_at=row.created_at,
        request=request_meta,
        solution=solution,
        provider=row.provider,
        model=row.model,
        fallback_used=row.fallback_used,
    )


def delete_history_item(db: Session, solution_id: str) -> None:
    row = db.get(Solution, solution_id)
    if row is None:
        raise AppError("history_not_found", "Solution not found in history.", status_code=404)
    db.delete(row)
    db.commit()
