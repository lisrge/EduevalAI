from __future__ import annotations

from datetime import datetime
from pathlib import Path

import hashlib

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import get_db
from app.models.application import ApplicationRecord, ScoreResult
from app.models.group import UserGroup
from app.models.request import UserChangeRequest
from app.models.user import User
from app.schemas.application import (
    ApplicationDetail,
    ApplicationInfo,
    ApplicationSummary,
    BatchDeletePayload,
    BatchDeleteResponse,
    BatchScoreItem,
    BatchScorePayload,
    BatchScoreResponse,
    CreateUserRequestPayload,
    ExtractionInfo,
    MyApplicationStatus,
    ScoreInfo,
    ScoreResponse,
    UploadResponse,
    UserChangeRequestItem,
)
from app.services.auth_service import get_user_by_token
from app.services.file_service import save_upload_file, save_user_file
from app.services.preview_service import PreviewError, get_preview_file
from app.services.scoring_service import score_application_text
from app.services.text_extractor import extract_text

router = APIRouter(prefix="/applications", tags=["applications"])


def _utcnow() -> datetime:
    return datetime.utcnow()


def _build_application_info(record: ApplicationRecord) -> ApplicationInfo:
    group_name = getattr(record, "_group_name", "") or ""
    preview_url = None
    if record.file_type in {"pdf", "docx"}:
        preview_url = f"/api/applications/{record.id}/preview"

    return ApplicationInfo(
        id=record.id,
        group_id=record.group_id,
        group_name=group_name,
        student_name=record.student_name,
        student_id=record.student_id,
        project_title=record.project_title,
        file_name=record.file_name,
        file_type=record.file_type,
        file_download_url=f"/api/applications/{record.id}/file",
        preview_url=preview_url,
        score_status=record.score_status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _build_extraction_info(record: ApplicationRecord) -> ExtractionInfo:
    return ExtractionInfo(
        status=record.text_extract_status,
        text_content=record.text_content,
        extract_error=record.extract_error,
        text_length=len(record.text_content or ""),
    )


def _build_score_info(score: ScoreResult | None) -> ScoreInfo | None:
    if not score:
        return None
    return ScoreInfo(
        rubric_version=score.rubric_version,
        model_name=score.model_name,
        prompt_version=score.prompt_version,
        practicality_score=score.practicality_score,
        innovation_score=score.innovation_score,
        total_score=score.total_score,
        practicality_reason=score.practicality_reason,
        innovation_reason=score.innovation_reason,
        strengths=score.strengths,
        weaknesses=score.weaknesses,
        needs_human_review=score.needs_human_review,
        scored_at=score.scored_at,
    )


def _build_request_item(row: UserChangeRequest) -> UserChangeRequestItem:
    return UserChangeRequestItem(
        id=row.id,
        request_type=row.request_type,
        status=row.status,
        request_note=row.request_note or "",
        file_name=row.file_name or "",
        review_note=row.review_note or "",
        reviewed_by_admin_id=row.reviewed_by_admin_id,
        reviewed_at=row.reviewed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_summary(record: ApplicationRecord) -> ApplicationSummary:
    score = record.score_result
    group_name = getattr(record, "_group_name", "") or ""
    preview_url = f"/api/applications/{record.id}/preview" if record.file_type in {"pdf", "docx"} else None
    return ApplicationSummary(
        id=record.id,
        group_id=record.group_id,
        group_name=group_name,
        student_name=record.student_name,
        student_id=record.student_id,
        project_title=record.project_title,
        score_status=record.score_status,
        practicality_score=score.practicality_score if score else None,
        innovation_score=score.innovation_score if score else None,
        total_score=score.total_score if score else None,
        needs_human_review=score.needs_human_review if score else None,
        updated_at=record.updated_at,
        file_name=record.file_name,
        file_type=record.file_type,
        file_download_url=f"/api/applications/{record.id}/file",
        preview_url=preview_url,
        created_at=record.created_at,
    )


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    value = authorization.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return ""


def _current_user(authorization: str | None, db: Session) -> User:
    token = _bearer_token(authorization)
    return get_user_by_token(db, token)


def _is_admin(user: User) -> bool:
    return user.role == "admin"


def _can_access_record(user: User, record: ApplicationRecord) -> bool:
    if _is_admin(user):
        return True
    if record.uploader_user_id and record.uploader_user_id == user.id:
        return True
    if record.student_id and record.student_id == user.student_id:
        return True
    return False


def _pending_request_exists(db: Session, user_id: int, request_type: str) -> bool:
    return (
        db.query(UserChangeRequest)
        .filter(
            UserChangeRequest.user_id == user_id,
            UserChangeRequest.request_type == request_type,
            UserChangeRequest.status == "pending",
        )
        .first()
        is not None
    )


def _attach_group_names(db: Session, records: list[ApplicationRecord]) -> None:
    group_ids = {record.group_id for record in records if record.group_id}
    if not group_ids:
        return
    mapping = {row.id: row.name for row in db.query(UserGroup).filter(UserGroup.id.in_(group_ids)).all()}
    for record in records:
        record._group_name = mapping.get(record.group_id or 0, "")


async def _create_application_record(
    upload_file: UploadFile,
    db: Session,
    uploader_user_id: int | None = None,
    student_name: str | None = None,
    student_id: str | None = None,
    project_title: str | None = None,
) -> ApplicationRecord:
    try:
        file_path, original_name = await save_upload_file(upload_file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    file_hash = None
    try:
        file_hash = _sha256_file(file_path)
    except OSError:
        file_hash = None

    if file_hash:
        existed = db.query(ApplicationRecord).filter(ApplicationRecord.file_hash == file_hash).first()
        if existed:
            try:
                Path(file_path).unlink(missing_ok=True)
            except OSError:
                pass
            raise HTTPException(status_code=409, detail="duplicate application")

    text_content, extract_error = extract_text(file_path)
    if text_content:
        extract_status = "ready_for_scoring"
        score_status = "ready_for_scoring"
    else:
        extract_status = "extract_failed"
        score_status = "extract_failed"

    record = ApplicationRecord(
        uploader_user_id=uploader_user_id,
        group_id=None,
        student_name=(student_name.strip() if isinstance(student_name, str) and student_name.strip() else "unknown"),
        student_id=(student_id.strip() if isinstance(student_id, str) and student_id.strip() else "unknown"),
        project_title=(project_title.strip() if isinstance(project_title, str) and project_title.strip() else "unknown"),
        file_name=original_name,
        file_path=file_path,
        file_type=(original_name.rsplit(".", 1)[-1].lower() if "." in original_name else "unknown"),
        file_hash=file_hash,
        text_extract_status=extract_status,
        text_content=text_content,
        extract_error=extract_error,
        score_status=score_status,
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


async def _score_record(record: ApplicationRecord, db: Session) -> ScoreInfo:
    payload = await score_application_text(record.text_content)

    if record.score_result:
        score = record.score_result
        score.model_name = payload.model_name
        score.practicality_score = payload.practicality_score
        score.innovation_score = payload.innovation_score
        score.total_score = payload.total_score
        score.practicality_reason = payload.practicality_reason
        score.innovation_reason = payload.innovation_reason
        score.strengths = payload.strengths
        score.weaknesses = payload.weaknesses
        score.needs_human_review = payload.needs_human_review
        score.scored_at = _utcnow()
    else:
        score = ScoreResult(
            application_id=record.id,
            rubric_version="v1.0",
            model_name=payload.model_name,
            prompt_version="v1.0",
            practicality_score=payload.practicality_score,
            innovation_score=payload.innovation_score,
            total_score=payload.total_score,
            practicality_reason=payload.practicality_reason,
            innovation_reason=payload.innovation_reason,
            strengths=payload.strengths,
            weaknesses=payload.weaknesses,
            needs_human_review=payload.needs_human_review,
            scored_at=_utcnow(),
        )
        db.add(score)

    record.score_status = "scored"
    record.updated_at = _utcnow()
    db.commit()
    db.refresh(record)
    return _build_score_info(record.score_result)


@router.get("", response_model=list[ApplicationSummary])
def list_applications(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    query = db.query(ApplicationRecord)
    if not _is_admin(user):
        query = query.filter(
            or_(
                ApplicationRecord.uploader_user_id == user.id,
                ApplicationRecord.student_id == user.student_id,
            )
        )
    records = query.order_by(ApplicationRecord.updated_at.desc()).all()
    _attach_group_names(db, records)
    items = [_to_summary(r) for r in records]
    if _is_admin(user):
        return items
    for item in items:
        item.practicality_score = None
        item.innovation_score = None
        item.total_score = None
        item.needs_human_review = None
    return items


@router.get("/{application_id}", response_model=ApplicationDetail)
def get_application(
    application_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    record = db.query(ApplicationRecord).filter(ApplicationRecord.id == application_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")
    if not _can_access_record(user, record):
        raise HTTPException(status_code=403, detail="forbidden")
    _attach_group_names(db, [record])
    score = _build_score_info(record.score_result) if _is_admin(user) else None
    return ApplicationDetail(
        application=_build_application_info(record),
        extraction=_build_extraction_info(record),
        score=score,
    )


@router.get("/{application_id}/file")
def download_application_file(
    application_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    record = db.query(ApplicationRecord).filter(ApplicationRecord.id == application_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")
    if not _can_access_record(user, record):
        raise HTTPException(status_code=403, detail="forbidden")

    file_path = Path(record.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Stored file not found")
    return FileResponse(path=file_path, filename=record.file_name)


@router.get("/{application_id}/preview")
def preview_application_file(
    application_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    record = db.query(ApplicationRecord).filter(ApplicationRecord.id == application_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")
    if not _can_access_record(user, record):
        raise HTTPException(status_code=403, detail="forbidden")

    try:
        preview = get_preview_file(record.file_path)
    except PreviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FileResponse(path=preview.path, media_type=preview.media_type, headers={"Content-Disposition": "inline"})


@router.post("/upload", response_model=UploadResponse)
async def upload_application(
    file: UploadFile = File(...),
    student_name: str | None = Form(default=None),
    student_id: str | None = Form(default=None),
    project_title: str | None = Form(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    if not _is_admin(user):
        student_id = user.student_id
    has_existing = (
        db.query(ApplicationRecord)
        .filter(
            or_(
                ApplicationRecord.uploader_user_id == user.id,
                ApplicationRecord.student_id == user.student_id,
            )
        )
        .first()
        is not None
    )
    if has_existing and not user.application_reupload_allowed:
        raise HTTPException(status_code=403, detail="application already uploaded; request admin approval before reupload")
    if not student_id:
        student_id = user.student_id
    record = await _create_application_record(
        file,
        db,
        uploader_user_id=user.id,
        student_name=student_name,
        student_id=student_id,
        project_title=project_title,
    )
    record.group_id = user.group_id
    db.commit()
    db.refresh(record)
    if user.group_id:
        group = db.query(UserGroup).filter(UserGroup.id == user.group_id).first()
        record._group_name = group.name if group else ""
    if user.application_reupload_allowed:
        user.application_reupload_allowed = False
        db.commit()
    return UploadResponse(
        message="Application uploaded successfully",
        application=_build_application_info(record),
        extraction=_build_extraction_info(record),
    )


@router.post("/{application_id}/score", response_model=ScoreResponse)
async def score_application(
    application_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="admin required")
    record = db.query(ApplicationRecord).filter(ApplicationRecord.id == application_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")
    score_info = await _score_record(record, db)
    return ScoreResponse(message="Application scored successfully", application_id=record.id, score=score_info)


@router.post("/score-batch", response_model=BatchScoreResponse)
async def score_batch(
    payload: BatchScorePayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="admin required")
    query = db.query(ApplicationRecord)
    if payload.application_ids:
        records = query.filter(ApplicationRecord.id.in_(payload.application_ids)).order_by(ApplicationRecord.id.asc()).all()
    else:
        records = query.filter(ApplicationRecord.score_status != "scored").order_by(ApplicationRecord.id.asc()).all()

    results: list[BatchScoreItem] = []
    total_scored = 0
    for record in records:
        try:
            score_info = await _score_record(record, db)
            results.append(BatchScoreItem(application_id=record.id, success=True, score=score_info))
            total_scored += 1
        except Exception as exc:
            db.rollback()
            results.append(BatchScoreItem(application_id=record.id, success=False, error=str(exc)))

    total_requested = len(payload.application_ids) if payload.application_ids else len(records)
    return BatchScoreResponse(
        message="Batch scoring completed",
        total_requested=total_requested,
        total_scored=total_scored,
        results=results,
    )


@router.delete("/batch", response_model=BatchDeleteResponse)
def delete_applications_batch(
    payload: BatchDeletePayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    if not payload.application_ids:
        raise HTTPException(status_code=400, detail="application_ids is required")

    records = db.query(ApplicationRecord).filter(ApplicationRecord.id.in_(payload.application_ids)).all()
    if not _is_admin(user):
        allowed = [r for r in records if _can_access_record(user, r)]
        if len(allowed) != len(records):
            raise HTTPException(status_code=403, detail="forbidden")
        records = allowed

    deleted_ids: list[int] = []
    for record in records:
        deleted_ids.append(record.id)
        try:
            file_path = Path(record.file_path)
            db.delete(record)
            db.commit()
            if file_path.exists():
                try:
                    file_path.unlink()
                except OSError:
                    pass
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return BatchDeleteResponse(message="Batch delete completed", deleted_ids=deleted_ids)


@router.get("/me/status", response_model=MyApplicationStatus)
def my_application_status(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    has_application = (
        db.query(ApplicationRecord)
        .filter(
            or_(
                ApplicationRecord.uploader_user_id == user.id,
                ApplicationRecord.student_id == user.student_id,
            )
        )
        .first()
        is not None
    )
    return MyApplicationStatus(
        has_application=has_application,
        application_reupload_allowed=bool(user.application_reupload_allowed),
        pending_reupload_request=_pending_request_exists(db, user.id, "application_reupload"),
        pending_signature_request=_pending_request_exists(db, user.id, "signature_update"),
    )


@router.get("/me/requests", response_model=list[UserChangeRequestItem])
def list_my_requests(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    rows = (
        db.query(UserChangeRequest)
        .filter(UserChangeRequest.user_id == user.id)
        .order_by(UserChangeRequest.created_at.desc())
        .all()
    )
    return [_build_request_item(row) for row in rows]


@router.post("/me/reupload-request", response_model=UserChangeRequestItem)
def create_reupload_request(
    payload: CreateUserRequestPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    has_application = (
        db.query(ApplicationRecord)
        .filter(
            or_(
                ApplicationRecord.uploader_user_id == user.id,
                ApplicationRecord.student_id == user.student_id,
            )
        )
        .first()
        is not None
    )
    if not has_application:
        raise HTTPException(status_code=400, detail="no application uploaded yet")
    if user.application_reupload_allowed:
        raise HTTPException(status_code=400, detail="reupload already approved")
    if _pending_request_exists(db, user.id, "application_reupload"):
        raise HTTPException(status_code=409, detail="reupload request already pending")
    row = UserChangeRequest(
        user_id=user.id,
        request_type="application_reupload",
        status="pending",
        request_note=(payload.request_note or "").strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _build_request_item(row)


@router.post("/me/signature-request", response_model=UserChangeRequestItem)
async def create_signature_request(
    signature: UploadFile = File(...),
    request_note: str | None = Form(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    if _pending_request_exists(db, user.id, "signature_update"):
        raise HTTPException(status_code=409, detail="signature request already pending")
    content_type = (signature.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="signature must be an image")
    try:
        file_path, file_name = await save_user_file(signature, "pending_signatures")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    row = UserChangeRequest(
        user_id=user.id,
        request_type="signature_update",
        status="pending",
        request_note=(request_note or "").strip(),
        file_name=file_name,
        file_path=file_path,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _build_request_item(row)
