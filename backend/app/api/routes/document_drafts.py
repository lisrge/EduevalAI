from __future__ import annotations

from datetime import datetime
from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.document_draft import ApplicationDraft, TaskDraft
from app.schemas.document_draft import DraftCreatePayload, DraftDetail, DraftSummary, DraftUpdatePayload
from app.services.auth_service import get_user_by_token
from app.services.document_draft_service import dumps_content, loads_content, render_application_docx, render_task_docx

router = APIRouter(prefix="/drafts", tags=["drafts"])


def _content_disposition_attachment(filename: str) -> str:
    raw = (filename or "document.docx").replace('"', "").strip()
    if not raw.lower().endswith(".docx"):
        raw = f"{raw}.docx"

    ascii_name = raw.encode("ascii", "ignore").decode("ascii").strip()
    if not ascii_name or ascii_name == ".docx" or ascii_name.startswith("."):
        ascii_name = "document.docx"
    if not ascii_name.lower().endswith(".docx"):
        ascii_name = f"{ascii_name}.docx"

    encoded = quote(raw, safe="")
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded}'


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    value = authorization.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return ""


def _current_user(authorization: str | None, db: Session):
    token = _bearer_token(authorization)
    return get_user_by_token(db, token)


def _summary_from_row(row) -> DraftSummary:
    return DraftSummary(
        id=row.id,
        group_id=row.group_id,
        title=row.title,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _detail_from_row(row) -> DraftDetail:
    return DraftDetail(
        id=row.id,
        title=row.title,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        content=loads_content(row.content_json),
    )


def _get_owned(db: Session, model, user_id: int, draft_id: int):
    row = db.query(model).filter(model.id == draft_id, model.user_id == user_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return row


@router.get("/applications", response_model=list[DraftSummary])
def list_application_drafts(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    user = _current_user(authorization, db)
    rows = (
        db.query(ApplicationDraft)
        .filter(ApplicationDraft.user_id == user.id)
        .order_by(ApplicationDraft.updated_at.desc())
        .all()
    )
    return [_summary_from_row(r) for r in rows]


@router.post("/applications", response_model=DraftDetail)
def create_application_draft(
    payload: DraftCreatePayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    row = ApplicationDraft(
        user_id=user.id,
        group_id=user.group_id,
        title=(payload.title or "未命名申请书").strip() or "未命名申请书",
        status="draft",
        content_json=dumps_content(payload.content),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _detail_from_row(row)


@router.get("/applications/{draft_id}", response_model=DraftDetail)
def get_application_draft(
    draft_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    row = _get_owned(db, ApplicationDraft, user.id, draft_id)
    return _detail_from_row(row)


@router.put("/applications/{draft_id}", response_model=DraftDetail)
def update_application_draft(
    draft_id: int,
    payload: DraftUpdatePayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    row = _get_owned(db, ApplicationDraft, user.id, draft_id)
    if payload.title is not None:
        row.title = payload.title.strip() or row.title
    if payload.status is not None:
        row.status = payload.status.strip() or row.status
    if payload.content is not None:
        row.content_json = dumps_content(payload.content)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _detail_from_row(row)


@router.delete("/applications/{draft_id}")
def delete_application_draft(
    draft_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    row = _get_owned(db, ApplicationDraft, user.id, draft_id)
    db.delete(row)
    db.commit()
    return {"message": "deleted"}


@router.get("/applications/{draft_id}/docx")
def export_application_docx(
    draft_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    row = _get_owned(db, ApplicationDraft, user.id, draft_id)
    content = loads_content(row.content_json)
    data = render_application_docx(content)
    filename = f"{row.title or '申请书'}.docx"
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": _content_disposition_attachment(filename)},
    )


@router.get("/tasks", response_model=list[DraftSummary])
def list_task_drafts(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    user = _current_user(authorization, db)
    rows = db.query(TaskDraft).filter(TaskDraft.user_id == user.id).order_by(TaskDraft.updated_at.desc()).all()
    return [_summary_from_row(r) for r in rows]


@router.post("/tasks", response_model=DraftDetail)
def create_task_draft(
    payload: DraftCreatePayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    row = TaskDraft(
        user_id=user.id,
        group_id=user.group_id,
        title=(payload.title or "未命名任务书").strip() or "未命名任务书",
        status="draft",
        content_json=dumps_content(payload.content),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _detail_from_row(row)


@router.get("/tasks/{draft_id}", response_model=DraftDetail)
def get_task_draft(
    draft_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    row = _get_owned(db, TaskDraft, user.id, draft_id)
    return _detail_from_row(row)


@router.put("/tasks/{draft_id}", response_model=DraftDetail)
def update_task_draft(
    draft_id: int,
    payload: DraftUpdatePayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    row = _get_owned(db, TaskDraft, user.id, draft_id)
    if payload.title is not None:
        row.title = payload.title.strip() or row.title
    if payload.status is not None:
        row.status = payload.status.strip() or row.status
    if payload.content is not None:
        row.content_json = dumps_content(payload.content)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _detail_from_row(row)


@router.delete("/tasks/{draft_id}")
def delete_task_draft(
    draft_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    row = _get_owned(db, TaskDraft, user.id, draft_id)
    db.delete(row)
    db.commit()
    return {"message": "deleted"}


@router.get("/tasks/{draft_id}/docx")
def export_task_docx(
    draft_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    row = _get_owned(db, TaskDraft, user.id, draft_id)
    content = loads_content(row.content_json)
    data = render_task_docx(content)
    filename = f"{row.title or '任务书'}.docx"
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": _content_disposition_attachment(filename)},
    )
