"""File upload analysis endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.models import FileMeta
from app.db.session import get_db
from app.schemas.api import FileMetaOut, WorkbookAnalysis
from app.services import files as files_service

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/analyze", response_model=WorkbookAnalysis)
async def analyze_file(
    file: UploadFile = File(...),
    consent: bool = Form(
        default=False,
        description="Acknowledges local analysis; per-request consent governs "
        "sending context to AI providers.",
    ),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> WorkbookAnalysis:
    """Analyze an uploaded .xlsx/.xlsm/.csv/.txt file locally.

    The file content is processed in a temporary location and deleted
    immediately; only the structured analysis is retained (with expiry).
    """
    if not consent:
        raise AppError(
            "consent_required",
            "Please confirm local analysis consent before uploading.",
            status_code=400,
        )
    filename = file.filename or "upload"
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise AppError(
            "file_too_large",
            f"File exceeds the {settings.max_upload_mb} MB upload limit.",
            status_code=413,
        )
    return await files_service.analyze_upload(db, filename, content, settings)


@router.get("", response_model=list[FileMetaOut])
async def list_files(db: Session = Depends(get_db)) -> list[FileMetaOut]:
    """List retained file analyses (content itself is never retained)."""
    files_service.purge_expired_files(db)
    rows = db.query(FileMeta).order_by(FileMeta.created_at.desc()).limit(50).all()
    return [
        FileMetaOut(
            file_id=r.id,
            filename=r.safe_name,
            file_type=r.file_type,
            size_bytes=r.size_bytes,
            status=r.status,
            created_at=r.created_at,
            expires_at=r.expires_at,
        )
        for r in rows
    ]


@router.delete("/{file_id}", status_code=204)
async def delete_file(file_id: str, db: Session = Depends(get_db)) -> None:
    files_service.delete_file(db, file_id)
