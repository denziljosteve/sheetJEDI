"""Saved solution history endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.api import HistoryPage, SolutionDetail
from app.services import history as history_service

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=HistoryPage)
async def list_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> HistoryPage:
    return history_service.list_history(db, limit=limit, offset=offset)


@router.get("/{solution_id}", response_model=SolutionDetail)
async def get_history_item(solution_id: str, db: Session = Depends(get_db)) -> SolutionDetail:
    return history_service.get_history_item(db, solution_id)


@router.delete("/{solution_id}", status_code=204)
async def delete_history_item(solution_id: str, db: Session = Depends(get_db)) -> None:
    history_service.delete_history_item(db, solution_id)
