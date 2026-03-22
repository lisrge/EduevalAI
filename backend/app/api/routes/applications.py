from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import get_db
from app.models.application import ApplicationRecord, ScoreResult
from app.schemas.application import (
    ApplicationDetail,
    ApplicationInfo,
    ApplicationSummary,
    BatchDeletePayload,
    BatchDeleteResponse,
    BatchScoreItem,
    BatchScorePayload,
    BatchScoreResponse,
    ExtractionInfo,
    ScoreInfo,
    ScoreResponse,
    UploadResponse,
)
from app.services.file_service import save_upload_file
from app.services.preview_service import PreviewError, get_preview_file
from app.services.scoring_service import score_application_text
from app.services.text_extractor import extract_text

router = APIRouter(prefix="/applications", tags=["applications"])


def _utcnow() -> datetime:
    return datetime.utcnow()


def _build_application_info(record: ApplicationRecord) -> ApplicationInfo:
    preview_url = None
    if record.file_type in {"pdf", "docx"}:
        preview_url = f"/api/applications/{record.id}/preview"

    return ApplicationInfo(
        id=record.id,
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


def _to_summary(record: ApplicationRecord) -> ApplicationSummary:
    score = record.score_result
    preview_url = f"/api/applications/{record.id}/preview" if record.file_type in {"pdf", "docx"} else None
    return ApplicationSummary(
        id=record.id,
        student_name=record.student_name,
        student_id=record.student_id,
        project_title=record.project_title,
        score_status=record.score_status,
        practicality_score=score.practicality_score if score else 0,
        innovation_score=score.innovation_score if score else 0,
        total_score=score.total_score if score else 0,
        needs_human_review=score.needs_human_review if score else True,
        updated_at=record.updated_at,
        file_name=record.file_name,
        file_type=record.file_type,
        file_download_url=f"/api/applications/{record.id}/file",
        preview_url=preview_url,
        created_at=record.created_at,
    )


async def _create_application_record(upload_file: UploadFile, db: Session) -> ApplicationRecord:
    try:
        file_path, original_name = await save_upload_file(upload_file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    text_content, extract_error = extract_text(file_path)
    if text_content:
        extract_status = "ready_for_scoring"
        score_status = "ready_for_scoring"
    else:
        extract_status = "extract_failed"
        score_status = "extract_failed"

    record = ApplicationRecord(
        student_name="unknown",
        student_id="unknown",
        project_title="unknown",
        file_name=original_name,
        file_path=file_path,
        file_type=(original_name.rsplit(".", 1)[-1].lower() if "." in original_name else "unknown"),
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
def list_applications(db: Session = Depends(get_db)):
    records = db.query(ApplicationRecord).order_by(ApplicationRecord.updated_at.desc()).all()
    return [_to_summary(r) for r in records]


@router.get("/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: int, db: Session = Depends(get_db)):
    record = db.query(ApplicationRecord).filter(ApplicationRecord.id == application_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")
    return ApplicationDetail(
        application=_build_application_info(record),
        extraction=_build_extraction_info(record),
        score=_build_score_info(record.score_result),
    )


@router.get("/{application_id}/file")
def download_application_file(application_id: int, db: Session = Depends(get_db)):
    record = db.query(ApplicationRecord).filter(ApplicationRecord.id == application_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")

    file_path = Path(record.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Stored file not found")
    return FileResponse(path=file_path, filename=record.file_name)


@router.get("/{application_id}/preview")
def preview_application_file(application_id: int, db: Session = Depends(get_db)):
    record = db.query(ApplicationRecord).filter(ApplicationRecord.id == application_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")

    try:
        preview = get_preview_file(record.file_path)
    except PreviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FileResponse(path=preview.path, media_type=preview.media_type, headers={"Content-Disposition": "inline"})


@router.post("/upload", response_model=UploadResponse)
async def upload_application(file: UploadFile = File(...), db: Session = Depends(get_db)):
    record = await _create_application_record(file, db)
    return UploadResponse(
        message="Application uploaded successfully",
        application=_build_application_info(record),
        extraction=_build_extraction_info(record),
    )


@router.post("/{application_id}/score", response_model=ScoreResponse)
async def score_application(application_id: int, db: Session = Depends(get_db)):
    record = db.query(ApplicationRecord).filter(ApplicationRecord.id == application_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")
    score_info = await _score_record(record, db)
    return ScoreResponse(message="Application scored successfully", application_id=record.id, score=score_info)


@router.post("/score-batch", response_model=BatchScoreResponse)
async def score_batch(payload: BatchScorePayload, db: Session = Depends(get_db)):
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
def delete_applications_batch(payload: BatchDeletePayload, db: Session = Depends(get_db)):
    if not payload.application_ids:
        raise HTTPException(status_code=400, detail="application_ids is required")

    records = db.query(ApplicationRecord).filter(ApplicationRecord.id.in_(payload.application_ids)).all()
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
