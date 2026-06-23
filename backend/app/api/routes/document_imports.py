from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session, selectinload

from app.db.base import get_db
from app.models.document_import import DocumentImportBatch, DocumentImportFile
from app.models.user import User
from app.schemas.document_import import (
    DocumentImportCommitResponse,
    DocumentImportCommitPayload,
    DocumentImportFileInfo,
    DocumentImportPreviewResponse,
    ImportedGroupPreview,
)
from app.services.auth_service import get_user_by_token
from app.services.document_import_service import commit_import_batch, merge_batch_groups, parse_import_file
from app.services.file_service import save_user_file

router = APIRouter(prefix="/document-imports", tags=["document-imports"])


def _token(authorization: str | None) -> str:
    value = (authorization or "").strip()
    return value[7:].strip() if value.lower().startswith("bearer ") else ""


def _admin(authorization: str | None, db: Session) -> User:
    user = get_user_by_token(db, _token(authorization))
    if str(user.role or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    return user


def _response(batch: DocumentImportBatch) -> DocumentImportPreviewResponse:
    return DocumentImportPreviewResponse(
        batch_id=batch.id,
        status=batch.status,
        files=[
            DocumentImportFileInfo(
                id=row.id,
                document_type=row.document_type,
                file_name=row.file_name,
                parse_status=row.parse_status,
                parse_error=row.parse_error,
            )
            for row in batch.files
        ],
        groups=[ImportedGroupPreview(**item) for item in merge_batch_groups(list(batch.files))],
        created_at=batch.created_at,
    )


@router.post("/admin/preview", response_model=DocumentImportPreviewResponse)
async def preview_document_import(
    files: list[UploadFile] = File(...),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    admin = _admin(authorization, db)
    if not files:
        raise HTTPException(status_code=400, detail="files are required")
    batch = DocumentImportBatch(created_by_user_id=admin.id, status="parsing")
    db.add(batch)
    db.commit()
    db.refresh(batch)
    seen_hashes: set[str] = set()
    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in {".docx", ".pdf", ".txt", ".md"}:
            continue
        file_path, file_name = await save_user_file(upload, f"document_imports/batch_{batch.id}")
        digest = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()
        if digest in seen_hashes:
            Path(file_path).unlink(missing_ok=True)
            continue
        seen_hashes.add(digest)
        parsed, error = parse_import_file(file_path, file_name)
        row = DocumentImportFile(
            batch_id=batch.id,
            document_type=parsed.get("document_type") or "unknown",
            file_name=file_name,
            file_path=file_path,
            file_hash=digest,
            parse_status="failed" if error else "parsed",
            parse_error=error or "",
            group_key=parsed.get("group_key") or "",
            parsed_json=json.dumps(parsed, ensure_ascii=False),
        )
        db.add(row)
    batch.status = "parsed"
    db.commit()
    batch = (
        db.query(DocumentImportBatch)
        .options(selectinload(DocumentImportBatch.files))
        .filter(DocumentImportBatch.id == batch.id)
        .first()
    )
    batch.group_count = len(merge_batch_groups(list(batch.files)))
    db.commit()
    return _response(batch)


@router.get("/admin/{batch_id}", response_model=DocumentImportPreviewResponse)
def get_document_import(
    batch_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _admin(authorization, db)
    batch = (
        db.query(DocumentImportBatch)
        .options(selectinload(DocumentImportBatch.files))
        .filter(DocumentImportBatch.id == batch_id)
        .first()
    )
    if not batch:
        raise HTTPException(status_code=404, detail="import batch not found")
    return _response(batch)


@router.post("/admin/{batch_id}/commit", response_model=DocumentImportCommitResponse)
def commit_document_import(
    batch_id: int,
    payload: DocumentImportCommitPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _admin(authorization, db)
    batch = (
        db.query(DocumentImportBatch)
        .options(selectinload(DocumentImportBatch.files))
        .filter(DocumentImportBatch.id == batch_id)
        .first()
    )
    if not batch:
        raise HTTPException(status_code=404, detail="import batch not found")
    if batch.status == "committed":
        raise HTTPException(status_code=409, detail="batch already committed")
    groups = [item.model_dump() for item in payload.groups] if payload.groups else None
    return DocumentImportCommitResponse(**commit_import_batch(db, batch, groups))
