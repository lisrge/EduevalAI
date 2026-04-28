from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.blog import BlogPost
from app.models.document_draft import ApplicationDraft, TaskDraft
from app.models.user import User
from app.schemas.document_draft import DraftDetail, DraftSummary
from app.schemas.user_profile import (
    AdminUserListItem,
    BlogCountInfo,
    BlogItem,
    ChangePasswordPayload,
    ChangePasswordResponse,
    ProfileResponse,
    UpdateUserRolePayload,
    UpdateUserRoleResponse,
)
from app.services.auth_service import change_password, get_user_by_token
from app.services.document_draft_service import (
    loads_content,
    render_application_docx,
    render_application_markdown,
    render_task_docx,
    render_task_markdown,
)

router = APIRouter(prefix="/users", tags=["users"])


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


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="admin required")


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


@router.get("/me/profile", response_model=ProfileResponse)
def me_profile(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    user = _current_user(authorization, db)
    return ProfileResponse(
        student_id=user.student_id,
        created_at=user.created_at,
        signature_file_name=user.signature_file_name,
        signature_url="/api/users/me/signature",
    )


@router.get("/me/signature")
def me_signature(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    user = _current_user(authorization, db)
    path = Path(user.signature_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="signature not found")
    return FileResponse(path=path, filename=user.signature_file_name, headers={"Content-Disposition": "inline"})


@router.post("/me/password", response_model=ChangePasswordResponse)
def me_change_password(
    payload: ChangePasswordPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    change_password(db, user, payload.old_password, payload.new_password)
    return ChangePasswordResponse(message="password updated")


@router.get("/admin/users", response_model=list[AdminUserListItem])
def admin_list_users(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    me = _current_user(authorization, db)
    _require_admin(me)

    app_counts = dict(
        db.query(ApplicationDraft.user_id, func.count(ApplicationDraft.id))
        .group_by(ApplicationDraft.user_id)
        .all()
    )
    task_counts = dict(
        db.query(TaskDraft.user_id, func.count(TaskDraft.id))
        .group_by(TaskDraft.user_id)
        .all()
    )
    blog_rows = (
        db.query(BlogPost.user_id, BlogPost.status, func.count(BlogPost.id))
        .group_by(BlogPost.user_id, BlogPost.status)
        .all()
    )
    blog_map: dict[int, dict[str, int]] = {}
    for uid, status, cnt in blog_rows:
        blog_map.setdefault(int(uid), {})[str(status or "").lower()] = int(cnt or 0)

    users = db.query(User).order_by(User.id.asc()).all()
    items: list[AdminUserListItem] = []
    for u in users:
        counts = blog_map.get(u.id, {})
        items.append(
            AdminUserListItem(
                id=u.id,
                student_id=u.student_id,
                role=u.role,
                is_root_admin=u.is_root_admin,
                blog=BlogCountInfo(
                    normal=int(counts.get("normal", 0)),
                    abnormal=int(counts.get("abnormal", 0)),
                ),
                application_draft_count=int(app_counts.get(u.id, 0) or 0),
                task_draft_count=int(task_counts.get(u.id, 0) or 0),
            )
        )
    return items


@router.put("/admin/users/{user_id}/role", response_model=UpdateUserRoleResponse)
def admin_update_role(
    user_id: int,
    payload: UpdateUserRolePayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)

    role = (payload.role or "").strip().lower()
    if role not in {"user", "admin"}:
        raise HTTPException(status_code=400, detail="invalid role")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    if user.is_root_admin:
        raise HTTPException(status_code=403, detail="initial admin role cannot be modified")

    user.role = role
    db.commit()
    return UpdateUserRoleResponse(id=user.id, role=user.role)


@router.get("/admin/users/{user_id}/drafts/applications", response_model=list[DraftSummary])
def admin_list_application_drafts(
    user_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    rows = db.query(ApplicationDraft).filter(ApplicationDraft.user_id == user_id).order_by(ApplicationDraft.updated_at.desc()).all()
    return [DraftSummary(id=r.id, title=r.title, status=r.status, created_at=r.created_at, updated_at=r.updated_at) for r in rows]


@router.get("/admin/users/{user_id}/drafts/tasks", response_model=list[DraftSummary])
def admin_list_task_drafts(
    user_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    rows = db.query(TaskDraft).filter(TaskDraft.user_id == user_id).order_by(TaskDraft.updated_at.desc()).all()
    return [DraftSummary(id=r.id, title=r.title, status=r.status, created_at=r.created_at, updated_at=r.updated_at) for r in rows]


@router.get("/admin/users/{user_id}/drafts/applications/{draft_id}", response_model=DraftDetail)
def admin_get_application_draft(
    user_id: int,
    draft_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    row = db.query(ApplicationDraft).filter(ApplicationDraft.id == draft_id, ApplicationDraft.user_id == user_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return DraftDetail(
        id=row.id,
        title=row.title,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        content=loads_content(row.content_json),
    )


@router.get("/admin/users/{user_id}/drafts/tasks/{draft_id}", response_model=DraftDetail)
def admin_get_task_draft(
    user_id: int,
    draft_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    row = db.query(TaskDraft).filter(TaskDraft.id == draft_id, TaskDraft.user_id == user_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return DraftDetail(
        id=row.id,
        title=row.title,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        content=loads_content(row.content_json),
    )


@router.get("/admin/users/{user_id}/drafts/applications/{draft_id}/docx")
def admin_export_application_docx(
    user_id: int,
    draft_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    row = db.query(ApplicationDraft).filter(ApplicationDraft.id == draft_id, ApplicationDraft.user_id == user_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    content = loads_content(row.content_json)
    data = render_application_docx(content)
    filename = f"{row.title or '申请书'}.docx"
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": _content_disposition_attachment(filename)},
    )


@router.get("/admin/users/{user_id}/drafts/tasks/{draft_id}/docx")
def admin_export_task_docx(
    user_id: int,
    draft_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    row = db.query(TaskDraft).filter(TaskDraft.id == draft_id, TaskDraft.user_id == user_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    content = loads_content(row.content_json)
    data = render_task_docx(content)
    filename = f"{row.title or '任务书'}.docx"
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": _content_disposition_attachment(filename)},
    )


@router.get("/admin/users/{user_id}/drafts/applications/{draft_id}/md")
def admin_preview_application_markdown(
    user_id: int,
    draft_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    row = db.query(ApplicationDraft).filter(ApplicationDraft.id == draft_id, ApplicationDraft.user_id == user_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    content = loads_content(row.content_json)
    md = render_application_markdown(content)
    return PlainTextResponse(md, media_type="text/markdown; charset=utf-8")


@router.get("/admin/users/{user_id}/drafts/tasks/{draft_id}/md")
def admin_preview_task_markdown(
    user_id: int,
    draft_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    row = db.query(TaskDraft).filter(TaskDraft.id == draft_id, TaskDraft.user_id == user_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    content = loads_content(row.content_json)
    md = render_task_markdown(content)
    return PlainTextResponse(md, media_type="text/markdown; charset=utf-8")


@router.get("/admin/users/{user_id}/blogs", response_model=list[BlogItem])
def admin_list_user_blogs(
    user_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    rows = db.query(BlogPost).filter(BlogPost.user_id == user_id).order_by(BlogPost.updated_at.desc()).all()
    return [BlogItem(id=r.id, title=r.title, url=r.url or "", status=r.status) for r in rows]


@router.get("/admin/users/{user_id}/blogs/{blog_id}/md")
def admin_get_blog_markdown(
    user_id: int,
    blog_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    row = db.query(BlogPost).filter(BlogPost.id == blog_id, BlogPost.user_id == user_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return PlainTextResponse(row.content_md or "", media_type="text/markdown; charset=utf-8")
