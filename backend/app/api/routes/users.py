from __future__ import annotations

from datetime import datetime
import re
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.application import ApplicationRecord
from app.models.blog import BlogCrawlRun, BlogPost
from app.models.document_draft import ApplicationDraft, TaskDraft
from app.models.group import UserGroup
from app.models.request import UserChangeRequest
from app.models.user import TeacherScore, User
from app.schemas.document_draft import DraftDetail, DraftSummary
from app.schemas.application import AdminUserChangeRequestItem, UserChangeRequestItem
from app.schemas.user_profile import (
    AdminBlogCrawlRunItem,
    BatchBlogCrawlPayload,
    AdminRequestReviewPayload,
    AdminUserListItem,
    BlogCountInfo,
    BlogCrawlRunItem,
    BlogDetail,
    BlogItem,
    BlogReviewPayload,
    BlogReviewResponse,
    ChangePasswordPayload,
    ChangePasswordResponse,
    GroupCreatePayload,
    GroupBootstrapPayload,
    GroupItem,
    GroupUpdatePayload,
    ProfileResponse,
    UpdateUserBasicProfilePayload,
    UpdateUserRolePayload,
    UpdateUserRoleResponse,
    UserGroupAssignPayload,
    UserBlogProfilePayload,
    UserBlogProfileResponse,
    TeacherScorePayload,
    TeacherScoreResponse,
    TeacherStudentDetail,
    TeacherStudentListItem,
)
from app.services.auth_service import change_password, get_user_by_token
from app.services.blog_crawler_service import run_user_blog_crawl
from app.services.csdn_crawler_service import cleanup_csdn_extracted_text, normalize_csdn_home_input
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


def _current_user_from_header_or_query(authorization: str | None, access_token: str | None, db: Session):
    token = (access_token or "").strip() or _bearer_token(authorization)
    return get_user_by_token(db, token)


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="admin required")


def _require_staff(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="admin required")


def _build_blog_profile_response(user: User) -> UserBlogProfileResponse:
    return UserBlogProfileResponse(
        id=user.id,
        student_id=user.student_id,
        blog_home_url=user.blog_home_url or "",
        blog_enabled=bool(user.blog_enabled),
        blog_crawl_status=user.blog_crawl_status or "idle",
        blog_last_crawled_at=user.blog_last_crawled_at,
    )


def _build_blog_run_item(row: BlogCrawlRun) -> BlogCrawlRunItem:
    return BlogCrawlRunItem(
        id=row.id,
        user_id=row.user_id,
        blog_home_url=row.blog_home_url,
        status=row.status,
        total_found=row.total_found,
        total_saved=row.total_saved,
        total_failed=row.total_failed,
        error_message=row.error_message or "",
        started_at=row.started_at,
        finished_at=row.finished_at,
        created_at=row.created_at,
    )


def _build_user_request_item(row: UserChangeRequest) -> UserChangeRequestItem:
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


def _build_admin_user_request_item(row: UserChangeRequest, student_id: str) -> AdminUserChangeRequestItem:
    return AdminUserChangeRequestItem(
        id=row.id,
        user_id=row.user_id,
        student_id=student_id,
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


def _build_admin_blog_run_item(row: BlogCrawlRun, student_id: str) -> AdminBlogCrawlRunItem:
    return AdminBlogCrawlRunItem(
        id=row.id,
        user_id=row.user_id,
        student_id=student_id,
        blog_home_url=row.blog_home_url,
        status=row.status,
        total_found=row.total_found,
        total_saved=row.total_saved,
        total_failed=row.total_failed,
        error_message=row.error_message or "",
        started_at=row.started_at,
        finished_at=row.finished_at,
        created_at=row.created_at,
    )


def _resolve_group_leader_user(db: Session, leader_student_id: str | None) -> User | None:
    sid = (leader_student_id or "").strip()
    if not sid:
        return None
    user = db.query(User).filter(User.student_id == sid).first()
    if not user:
        raise HTTPException(status_code=404, detail="leader user not found")
    return user


def _canonical_group_name(group_number: int) -> str:
    return f"\u7b2c{int(group_number)}\u7ec4"


def _canonical_group_code(group_number: int) -> str:
    return f"G{int(group_number):03d}"


def _build_group_item(
    row: UserGroup,
    member_count: int = 0,
    leader_name: str = "",
    leader_project_title: str = "",
) -> GroupItem:
    return GroupItem(
        id=row.id,
        group_number=row.group_number,
        name=_canonical_group_name(row.group_number),
        code=_canonical_group_code(row.group_number),
        leader_user_id=row.leader_user_id,
        leader_name=leader_name,
        leader_project_title=leader_project_title,
        member_count=member_count,
        description=row.description or "",
    )


def _extract_blog_preview_html(row: BlogPost) -> str:
    file_path = Path(row.raw_html_path or "")
    if not file_path.exists():
        return ""
    try:
        raw_html = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

    patterns = [
        r'<div[^>]+id="content_views"[^>]*>(?P<body>[\s\S]*?)</div>\s*</div>',
        r'<div[^>]+class="markdown_views[^"]*"[^>]*>(?P<body>[\s\S]*?)</div>\s*</div>',
        r'<div[^>]+class="htmledit_views[^"]*"[^>]*>(?P<body>[\s\S]*?)</div>\s*</div>',
    ]
    fragment = ""
    for pattern in patterns:
        match = re.search(pattern, raw_html, flags=re.IGNORECASE)
        if match:
            fragment = match.group("body")
            break
    if not fragment:
        return ""

    cleaned = re.sub(r"<script[\s\S]*?</script>", "", fragment, flags=re.IGNORECASE)
    cleaned = re.sub(r"<style[\s\S]*?</style>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\son\w+\s*=\s*(['\"]).*?\1", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'javascript:', "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _build_user_profile_map(db: Session) -> dict[int, dict[str, str]]:
    user_rows = db.query(User.id, User.real_name).all()
    mapping: dict[int, dict[str, str]] = {
        int(row.id): {
            "student_name": (row.real_name or "").strip(),
            "project_title": "",
        }
        for row in user_rows
        if row.id
    }
    rows = (
        db.query(ApplicationRecord.uploader_user_id, func.max(ApplicationRecord.id))
        .filter(ApplicationRecord.uploader_user_id.isnot(None))
        .group_by(ApplicationRecord.uploader_user_id)
        .all()
    )
    latest_ids = [row[1] for row in rows if row[1]]
    if not latest_ids:
        return mapping
    latest_records = (
        db.query(
            ApplicationRecord.id,
            ApplicationRecord.uploader_user_id,
            ApplicationRecord.student_name,
            ApplicationRecord.project_title,
        )
        .filter(ApplicationRecord.id.in_(latest_ids))
        .all()
    )
    for row in latest_records:
        if not row.uploader_user_id:
            continue
        user_id = int(row.uploader_user_id)
        item = mapping.setdefault(user_id, {"student_name": "", "project_title": ""})
        if not item.get("student_name"):
            item["student_name"] = (row.student_name or "").strip()
        item["project_title"] = (row.project_title or "").strip()
    return mapping


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
    pending_reupload_request = (
        db.query(UserChangeRequest)
        .filter(
            UserChangeRequest.user_id == user.id,
            UserChangeRequest.request_type == "application_reupload",
            UserChangeRequest.status == "pending",
        )
        .first()
        is not None
    )
    pending_signature_request = (
        db.query(UserChangeRequest)
        .filter(
            UserChangeRequest.user_id == user.id,
            UserChangeRequest.request_type == "signature_update",
            UserChangeRequest.status == "pending",
        )
        .first()
        is not None
    )
    return ProfileResponse(
        student_id=user.student_id,
        real_name=user.real_name or "",
        created_at=user.created_at,
        signature_file_name=user.signature_file_name,
        signature_url="/api/users/me/signature",
        application_reupload_allowed=bool(user.application_reupload_allowed),
        pending_reupload_request=pending_reupload_request,
        pending_signature_request=pending_signature_request,
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
    request_rows = (
        db.query(UserChangeRequest.user_id, UserChangeRequest.request_type, func.count(UserChangeRequest.id))
        .filter(UserChangeRequest.status == "pending")
        .group_by(UserChangeRequest.user_id, UserChangeRequest.request_type)
        .all()
    )
    blog_map: dict[int, dict[str, int]] = {}
    for uid, status, cnt in blog_rows:
        blog_map.setdefault(int(uid), {})[str(status or "").lower()] = int(cnt or 0)
    request_map: dict[int, dict[str, int]] = {}
    for uid, request_type, cnt in request_rows:
        request_map.setdefault(int(uid), {})[str(request_type or "").lower()] = int(cnt or 0)

    group_rows = db.query(UserGroup).all()
    group_map = {row.id: row for row in group_rows}
    user_profile_map = _build_user_profile_map(db)
    users = db.query(User).order_by(User.id.asc()).all()
    items: list[AdminUserListItem] = []
    for u in users:
        counts = blog_map.get(u.id, {})
        group_row = group_map.get(u.group_id or 0)
        user_profile = user_profile_map.get(u.id, {})
        leader_profile = user_profile_map.get(group_row.leader_user_id, {}) if group_row and group_row.leader_user_id else {}
        items.append(
            AdminUserListItem(
                id=u.id,
                student_id=u.student_id,
                display_name=user_profile.get("student_name", ""),
                project_title=user_profile.get("project_title", ""),
                role=u.role,
                is_root_admin=u.is_root_admin,
                group_id=u.group_id,
                group_number=group_row.group_number if group_row else None,
                group_name=_canonical_group_name(group_row.group_number) if group_row else "",
                group_leader_name=leader_profile.get("student_name", ""),
                group_project_title=leader_profile.get("project_title", ""),
                blog=BlogCountInfo(
                    normal=int(counts.get("normal", 0)),
                    abnormal=int(counts.get("abnormal", 0)),
                ),
                blog_home_url=u.blog_home_url or "",
                blog_enabled=bool(u.blog_enabled),
                blog_crawl_status=u.blog_crawl_status or "idle",
                blog_last_crawled_at=u.blog_last_crawled_at,
                application_reupload_allowed=bool(u.application_reupload_allowed),
                pending_reupload_request_count=int(request_map.get(u.id, {}).get("application_reupload", 0)),
                pending_signature_request_count=int(request_map.get(u.id, {}).get("signature_update", 0)),
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

    if int(user_id) == int(me.id):
        raise HTTPException(status_code=403, detail="cannot modify your own role")

    role = (payload.role or "").strip().lower()
    if role not in {"user", "admin", "teacher"}:
        raise HTTPException(status_code=400, detail="invalid role")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    if user.is_root_admin:
        raise HTTPException(status_code=403, detail="initial admin role cannot be modified")

    user.role = role
    db.commit()
    return UpdateUserRoleResponse(id=user.id, role=user.role)


@router.get("/teacher/students", response_model=list[TeacherStudentListItem])
def teacher_list_students(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_staff(me)

    users = db.query(User).filter(User.role == "user").order_by(User.group_id.asc().nulls_last(), User.id.asc()).all()
    if not users:
        return []

    user_profile_map = _build_user_profile_map(db)
    group_rows = db.query(UserGroup).all()
    group_map = {row.id: row for row in group_rows}

    blog_rows = (
        db.query(BlogPost.user_id, BlogPost.status, func.count(BlogPost.id))
        .filter(BlogPost.user_id.in_([u.id for u in users]))
        .group_by(BlogPost.user_id, BlogPost.status)
        .all()
    )
    blog_map: dict[int, dict[str, int]] = {}
    for uid, status, cnt in blog_rows:
        blog_map.setdefault(int(uid), {})[str(status or "").lower()] = int(cnt or 0)

    score_rows = (
        db.query(TeacherScore)
        .filter(TeacherScore.teacher_user_id == me.id, TeacherScore.student_user_id.in_([u.id for u in users]))
        .all()
    )
    score_map = {int(row.student_user_id): row for row in score_rows}

    items: list[TeacherStudentListItem] = []
    for u in users:
        counts = blog_map.get(u.id, {})
        group_row = group_map.get(u.group_id or 0)
        profile = user_profile_map.get(u.id, {})
        score_row = score_map.get(u.id)
        items.append(
            TeacherStudentListItem(
                id=u.id,
                student_id=u.student_id,
                display_name=profile.get("student_name", ""),
                project_title=profile.get("project_title", ""),
                group_number=group_row.group_number if group_row else None,
                group_name=_canonical_group_name(group_row.group_number) if group_row and group_row.group_number else "",
                blog_home_url=u.blog_home_url or "",
                blog=BlogCountInfo(
                    normal=int(counts.get("normal", 0)),
                    abnormal=int(counts.get("abnormal", 0)),
                ),
                teacher_score=int(score_row.score) if score_row else None,
                teacher_score_note=(score_row.note or "") if score_row else "",
                teacher_scored_at=score_row.updated_at if score_row else None,
            )
        )
    return items


@router.get("/teacher/students/{student_user_id}", response_model=TeacherStudentDetail)
def teacher_get_student_detail(
    student_user_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_staff(me)

    user = db.query(User).filter(User.id == student_user_id, User.role == "user").first()
    if not user:
        raise HTTPException(status_code=404, detail="student not found")

    group_row = db.query(UserGroup).filter(UserGroup.id == user.group_id).first() if user.group_id else None
    profile = _build_user_profile_map(db).get(user.id, {})

    blogs = db.query(BlogPost).filter(BlogPost.user_id == user.id).order_by(BlogPost.published_at.desc().nulls_last(), BlogPost.id.desc()).all()
    blog_items = [
        BlogItem(
            id=row.id,
            title=row.title,
            url=row.url,
            status=row.status,
            source=row.source,
            published_at=row.published_at,
            capture_status=row.capture_status,
            review_status=row.review_status,
            has_screenshot=bool(row.screenshot_path),
            has_html=bool(row.raw_html_path),
            updated_at=row.updated_at,
        )
        for row in blogs
    ]
    work_summary = "\n".join([s for s in [(row.summary or "").strip() for row in blogs[:6]] if s])[:2000]

    score_row = (
        db.query(TeacherScore)
        .filter(TeacherScore.teacher_user_id == me.id, TeacherScore.student_user_id == user.id)
        .first()
    )

    return TeacherStudentDetail(
        id=user.id,
        student_id=user.student_id,
        display_name=profile.get("student_name", ""),
        project_title=profile.get("project_title", ""),
        group_number=group_row.group_number if group_row else None,
        group_name=_canonical_group_name(group_row.group_number) if group_row and group_row.group_number else "",
        blog_home_url=user.blog_home_url or "",
        blogs=blog_items,
        work_summary=work_summary,
        teacher_score=int(score_row.score) if score_row else None,
        teacher_score_note=(score_row.note or "") if score_row else "",
        teacher_scored_at=score_row.updated_at if score_row else None,
    )


@router.put("/teacher/students/{student_user_id}/score", response_model=TeacherScoreResponse)
def teacher_score_student(
    student_user_id: int,
    payload: TeacherScorePayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_staff(me)

    student = db.query(User).filter(User.id == student_user_id, User.role == "user").first()
    if not student:
        raise HTTPException(status_code=404, detail="student not found")

    score = int(payload.score)
    if score < 0 or score > 100:
        raise HTTPException(status_code=400, detail="score must be between 0 and 100")

    note = (payload.note or "").strip()
    row = (
        db.query(TeacherScore)
        .filter(TeacherScore.teacher_user_id == me.id, TeacherScore.student_user_id == student.id)
        .first()
    )
    now = datetime.utcnow()
    if row is None:
        row = TeacherScore(
            teacher_user_id=me.id,
            student_user_id=student.id,
            score=score,
            note=note,
            updated_at=now,
        )
        db.add(row)
    else:
        row.score = score
        row.note = note
        row.updated_at = now
    db.commit()
    db.refresh(row)
    return TeacherScoreResponse(
        student_user_id=row.student_user_id,
        score=row.score,
        note=row.note or "",
        updated_at=row.updated_at,
    )


@router.put("/admin/users/{user_id}/basic-profile", response_model=AdminUserListItem)
def admin_update_user_basic_profile(
    user_id: int,
    payload: UpdateUserBasicProfilePayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    user.real_name = (payload.real_name or "").strip()
    db.commit()
    db.refresh(user)

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
        .filter(BlogPost.user_id == user.id)
        .group_by(BlogPost.user_id, BlogPost.status)
        .all()
    )
    counts = {str(status or "").lower(): int(cnt or 0) for _, status, cnt in blog_rows}
    request_rows = (
        db.query(UserChangeRequest.request_type, func.count(UserChangeRequest.id))
        .filter(UserChangeRequest.user_id == user.id, UserChangeRequest.status == "pending")
        .group_by(UserChangeRequest.request_type)
        .all()
    )
    request_map = {str(request_type or "").lower(): int(cnt or 0) for request_type, cnt in request_rows}

    group = db.query(UserGroup).filter(UserGroup.id == user.group_id).first() if user.group_id else None
    user_profile = _build_user_profile_map(db).get(user.id, {})
    leader_profile = _build_user_profile_map(db).get(group.leader_user_id, {}) if group and group.leader_user_id else {}

    return AdminUserListItem(
        id=user.id,
        student_id=user.student_id,
        display_name=user_profile.get("student_name", ""),
        project_title=user_profile.get("project_title", ""),
        role=user.role,
        is_root_admin=user.is_root_admin,
        group_id=user.group_id,
        group_number=group.group_number if group else None,
        group_name=_canonical_group_name(group.group_number) if group else "",
        group_leader_name=leader_profile.get("student_name", ""),
        group_project_title=leader_profile.get("project_title", ""),
        blog=BlogCountInfo(
            normal=int(counts.get("normal", 0)),
            abnormal=int(counts.get("abnormal", 0)),
        ),
        blog_home_url=user.blog_home_url or "",
        blog_enabled=bool(user.blog_enabled),
        blog_crawl_status=user.blog_crawl_status or "idle",
        blog_last_crawled_at=user.blog_last_crawled_at,
        application_reupload_allowed=bool(user.application_reupload_allowed),
        pending_reupload_request_count=int(request_map.get("application_reupload", 0)),
        pending_signature_request_count=int(request_map.get("signature_update", 0)),
        application_draft_count=int(app_counts.get(user.id, 0) or 0),
        task_draft_count=int(task_counts.get(user.id, 0) or 0),
    )


@router.get("/admin/groups", response_model=list[GroupItem])
def admin_list_groups(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    rows = db.query(UserGroup).order_by(UserGroup.group_number.asc(), UserGroup.id.asc()).all()
    user_profile_map = _build_user_profile_map(db)
    member_rows = dict(
        db.query(User.group_id, func.count(User.id))
        .filter(User.group_id.isnot(None))
        .group_by(User.group_id)
        .all()
    )
    return [
        _build_group_item(
            row,
            member_count=int(member_rows.get(row.id, 0) or 0),
            leader_name=user_profile_map.get(row.leader_user_id, {}).get("student_name", ""),
            leader_project_title=user_profile_map.get(row.leader_user_id, {}).get("project_title", ""),
        )
        for row in rows
    ]


@router.post("/admin/groups", response_model=GroupItem)
def admin_create_group(
    payload: GroupCreatePayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    if payload.group_number <= 0:
        raise HTTPException(status_code=400, detail="group_number must be positive")
    existed = db.query(UserGroup).filter(UserGroup.group_number == payload.group_number).first()
    if existed:
        raise HTTPException(status_code=409, detail="group already exists")
    leader = _resolve_group_leader_user(db, payload.leader_student_id)
    row = UserGroup(
        group_number=payload.group_number,
        name=_canonical_group_name(payload.group_number),
        code=_canonical_group_code(payload.group_number),
        leader_user_id=leader.id if leader else None,
        description=(payload.description or "").strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    leader_name = ""
    leader_project_title = ""
    if leader:
        leader_profile = _build_user_profile_map(db).get(leader.id, {})
        leader_name = leader_profile.get("student_name", "")
        leader_project_title = leader_profile.get("project_title", "")
    return _build_group_item(row, member_count=0, leader_name=leader_name, leader_project_title=leader_project_title)


@router.put("/admin/groups/{group_id}", response_model=GroupItem)
def admin_update_group(
    group_id: int,
    payload: GroupUpdatePayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    row = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="group not found")
    leader = _resolve_group_leader_user(db, payload.leader_student_id)
    row.leader_user_id = leader.id if leader else None
    row.description = (payload.description or "").strip()
    db.commit()
    db.refresh(row)
    member_count = db.query(func.count(User.id)).filter(User.group_id == row.id).scalar() or 0
    leader_profile = _build_user_profile_map(db).get(leader.id, {}) if leader else {}
    leader_name = leader_profile.get("student_name", "")
    leader_project_title = leader_profile.get("project_title", "")
    return _build_group_item(
        row,
        member_count=int(member_count),
        leader_name=leader_name,
        leader_project_title=leader_project_title,
    )


@router.delete("/admin/groups/{group_id}")
def admin_delete_group(
    group_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    row = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="group not found")

    db.query(User).filter(User.group_id == row.id).update({User.group_id: None}, synchronize_session=False)
    db.query(ApplicationDraft).filter(ApplicationDraft.group_id == row.id).update({ApplicationDraft.group_id: None}, synchronize_session=False)
    db.query(TaskDraft).filter(TaskDraft.group_id == row.id).update({TaskDraft.group_id: None}, synchronize_session=False)
    db.query(ApplicationRecord).filter(ApplicationRecord.group_id == row.id).update({ApplicationRecord.group_id: None}, synchronize_session=False)
    db.delete(row)
    db.commit()
    return {"id": group_id, "message": "group deleted"}


@router.post("/admin/groups/bootstrap", response_model=list[GroupItem])
def admin_bootstrap_groups(
    payload: GroupBootstrapPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    total_groups = max(1, min(int(payload.total_groups or 86), 200))
    existing_numbers = {row.group_number for row in db.query(UserGroup.group_number).all()}
    created: list[UserGroup] = []
    for group_number in range(1, total_groups + 1):
        if group_number in existing_numbers:
            continue
        row = UserGroup(
            group_number=group_number,
            name=_canonical_group_name(group_number),
            code=_canonical_group_code(group_number),
            description="",
        )
        db.add(row)
        created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)
    return [_build_group_item(row, member_count=0, leader_name="") for row in created]


@router.put("/admin/users/{user_id}/group", response_model=AdminUserListItem)
def admin_assign_user_group(
    user_id: int,
    payload: UserGroupAssignPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    group_name = ""
    group = None
    if payload.group_id is not None:
        group = db.query(UserGroup).filter(UserGroup.id == payload.group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="group not found")
        user.group_id = group.id
        group_name = _canonical_group_name(group.group_number)
    else:
        user.group_id = None
    db.commit()
    user_profile = _build_user_profile_map(db).get(user.id, {})
    leader_profile = _build_user_profile_map(db).get(group.leader_user_id, {}) if group and group.leader_user_id else {}
    return AdminUserListItem(
        id=user.id,
        student_id=user.student_id,
        display_name=user_profile.get("student_name", ""),
        project_title=user_profile.get("project_title", ""),
        role=user.role,
        is_root_admin=user.is_root_admin,
        group_id=user.group_id,
        group_number=group.group_number if group else None,
        group_name=group_name,
        group_leader_name=leader_profile.get("student_name", ""),
        group_project_title=leader_profile.get("project_title", ""),
        blog=BlogCountInfo(normal=0, abnormal=0),
        blog_home_url=user.blog_home_url or "",
        blog_enabled=bool(user.blog_enabled),
        blog_crawl_status=user.blog_crawl_status or "idle",
        blog_last_crawled_at=user.blog_last_crawled_at,
        application_reupload_allowed=bool(user.application_reupload_allowed),
        pending_reupload_request_count=0,
        pending_signature_request_count=0,
        application_draft_count=0,
        task_draft_count=0,
    )


@router.get("/admin/users/{user_id}/blog-profile", response_model=UserBlogProfileResponse)
def admin_get_blog_profile(
    user_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return _build_blog_profile_response(user)


@router.put("/admin/users/{user_id}/blog-profile", response_model=UserBlogProfileResponse)
def admin_update_blog_profile(
    user_id: int,
    payload: UserBlogProfilePayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    raw_blog_value = (payload.blog_home_url or "").strip()
    if raw_blog_value:
        try:
            user.blog_home_url = normalize_csdn_home_input(raw_blog_value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        user.blog_home_url = None
    user.blog_enabled = bool(payload.blog_enabled)
    db.commit()
    db.refresh(user)
    return _build_blog_profile_response(user)


@router.get("/admin/users/{user_id}/requests", response_model=list[UserChangeRequestItem])
def admin_list_user_requests(
    user_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    rows = (
        db.query(UserChangeRequest)
        .filter(UserChangeRequest.user_id == user_id)
        .order_by(UserChangeRequest.created_at.desc())
        .all()
    )
    return [_build_user_request_item(row) for row in rows]


@router.get("/admin/requests", response_model=list[AdminUserChangeRequestItem])
def admin_list_all_requests(
    status: str | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    query = db.query(UserChangeRequest, User.student_id).join(User, User.id == UserChangeRequest.user_id)
    normalized_status = (status or "").strip().lower()
    if normalized_status:
        query = query.filter(UserChangeRequest.status == normalized_status)
    rows = query.order_by(UserChangeRequest.created_at.desc()).all()
    return [_build_admin_user_request_item(row, student_id) for row, student_id in rows]


@router.put("/admin/users/{user_id}/requests/{request_id}/review", response_model=UserChangeRequestItem)
def admin_review_user_request(
    user_id: int,
    request_id: int,
    payload: AdminRequestReviewPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    row = (
        db.query(UserChangeRequest)
        .filter(UserChangeRequest.id == request_id, UserChangeRequest.user_id == user_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="request not found")
    status = (payload.status or "").strip().lower()
    if status not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="invalid status")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="request already reviewed")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    row.status = status
    row.review_note = payload.review_note or ""
    row.reviewed_by_admin_id = me.id
    row.reviewed_at = datetime.utcnow()

    if status == "approved":
        if row.request_type == "application_reupload":
            user.application_reupload_allowed = True
        elif row.request_type == "signature_update":
            if not row.file_path:
                raise HTTPException(status_code=400, detail="signature file missing")
            user.signature_file_name = row.file_name or user.signature_file_name
            user.signature_path = row.file_path

    db.commit()
    db.refresh(row)
    db.refresh(user)
    return _build_user_request_item(row)


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
    _require_staff(me)
    rows = db.query(BlogPost).filter(BlogPost.user_id == user_id).order_by(BlogPost.updated_at.desc()).all()
    return [
        BlogItem(
            id=r.id,
            title=r.title,
            url=r.url or "",
            status=r.status,
            source=r.source,
            published_at=r.published_at,
            capture_status=r.capture_status,
            review_status=r.review_status,
            has_screenshot=bool(r.screenshot_path),
            has_html=bool(r.raw_html_path),
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.post("/admin/users/{user_id}/blogs/crawl", response_model=BlogCrawlRunItem)
def admin_trigger_user_blog_crawl(
    user_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    try:
        run = run_user_blog_crawl(db=db, user=user, admin=me)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _build_blog_run_item(run)


@router.post("/admin/blogs/crawl-batch", response_model=list[BlogCrawlRunItem])
def admin_trigger_batch_blog_crawl(
    payload: BatchBlogCrawlPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    user_ids = [int(v) for v in payload.user_ids if int(v) > 0]
    if not user_ids:
        raise HTTPException(status_code=400, detail="user_ids is required")
    rows = db.query(User).filter(User.id.in_(user_ids)).order_by(User.id.asc()).all()
    found_ids = {row.id for row in rows}
    missing = [user_id for user_id in user_ids if user_id not in found_ids]
    if missing:
        raise HTTPException(status_code=404, detail=f"user not found: {missing[0]}")
    runs: list[BlogCrawlRunItem] = []
    for user in rows:
        try:
            run = run_user_blog_crawl(db=db, user=user, admin=me)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"{user.student_id}: {exc}") from exc
        runs.append(_build_blog_run_item(run))
    return runs


@router.get("/admin/users/{user_id}/blogs/crawl-runs", response_model=list[BlogCrawlRunItem])
def admin_list_user_blog_crawl_runs(
    user_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_staff(me)
    rows = db.query(BlogCrawlRun).filter(BlogCrawlRun.user_id == user_id).order_by(BlogCrawlRun.created_at.desc()).all()
    return [_build_blog_run_item(row) for row in rows]


@router.get("/admin/blogs/crawl-runs", response_model=list[AdminBlogCrawlRunItem])
def admin_list_all_blog_crawl_runs(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    rows = (
        db.query(BlogCrawlRun, User.student_id)
        .join(User, User.id == BlogCrawlRun.user_id)
        .order_by(BlogCrawlRun.created_at.desc())
        .all()
    )
    return [_build_admin_blog_run_item(row, student_id) for row, student_id in rows]


@router.get("/admin/users/{user_id}/blogs/{blog_id}", response_model=BlogDetail)
def admin_get_blog_detail(
    user_id: int,
    blog_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_staff(me)
    row = db.query(BlogPost).filter(BlogPost.id == blog_id, BlogPost.user_id == user_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return BlogDetail(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        url=row.url,
        source=row.source,
        summary=row.summary or "",
        content_md=cleanup_csdn_extracted_text(row.content_md or ""),
        content_text=cleanup_csdn_extracted_text(row.content_text or ""),
        published_at=row.published_at,
        capture_status=row.capture_status,
        capture_error=row.capture_error or "",
        capture_timestamp=row.capture_timestamp,
        review_status=row.review_status,
        review_note=row.review_note or "",
        screenshot_url=f"/api/users/admin/users/{user_id}/blogs/{blog_id}/screenshot",
        html_url=f"/api/users/admin/users/{user_id}/blogs/{blog_id}/html",
        content_preview_html=_extract_blog_preview_html(row),
    )


@router.get("/admin/users/{user_id}/blogs/{blog_id}/md")
def admin_get_blog_markdown(
    user_id: int,
    blog_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_staff(me)
    row = db.query(BlogPost).filter(BlogPost.id == blog_id, BlogPost.user_id == user_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    content = row.content_md or row.content_text or ""
    return PlainTextResponse(cleanup_csdn_extracted_text(content), media_type="text/markdown; charset=utf-8")


@router.get("/admin/users/{user_id}/blogs/{blog_id}/screenshot")
def admin_get_blog_screenshot(
    user_id: int,
    blog_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_staff(me)
    row = db.query(BlogPost).filter(BlogPost.id == blog_id, BlogPost.user_id == user_id).first()
    if not row or not row.screenshot_path:
        raise HTTPException(status_code=404, detail="screenshot not found")
    file_path = Path(row.screenshot_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="screenshot file not found")
    return FileResponse(path=file_path, filename=file_path.name, headers={"Content-Disposition": "inline"})


@router.get("/admin/users/{user_id}/blogs/{blog_id}/html")
def admin_get_blog_html(
    user_id: int,
    blog_id: int,
    authorization: str | None = Header(default=None),
    access_token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user_from_header_or_query(authorization, access_token, db)
    _require_staff(me)
    row = db.query(BlogPost).filter(BlogPost.id == blog_id, BlogPost.user_id == user_id).first()
    if not row or not row.raw_html_path:
        raise HTTPException(status_code=404, detail="html not found")
    file_path = Path(row.raw_html_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="html file not found")
    return FileResponse(path=file_path, filename=file_path.name, media_type="text/html; charset=utf-8")


@router.put("/admin/users/{user_id}/blogs/{blog_id}/review", response_model=BlogReviewResponse)
def admin_review_blog(
    user_id: int,
    blog_id: int,
    payload: BlogReviewPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)
    row = db.query(BlogPost).filter(BlogPost.id == blog_id, BlogPost.user_id == user_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    review_status = (payload.review_status or "").strip().lower()
    if review_status not in {"pending", "normal", "abnormal"}:
        raise HTTPException(status_code=400, detail="invalid review_status")
    row.review_status = review_status
    row.review_note = payload.review_note or ""
    row.reviewed_at = datetime.utcnow()
    row.reviewed_by_admin_id = me.id
    row.status = "abnormal" if review_status == "abnormal" else "normal"
    db.commit()
    db.refresh(row)
    return BlogReviewResponse(
        id=row.id,
        review_status=row.review_status,
        review_note=row.review_note or "",
        reviewed_at=row.reviewed_at,
        reviewed_by_admin_id=row.reviewed_by_admin_id,
    )
