from __future__ import annotations

from datetime import datetime
import shutil
from pathlib import Path
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.base import get_db
from app.models.blog import BlogPost
from app.models.code_analysis import SubmissionCodeAnalysis
from app.models.course import Assignment
from app.models.group import UserGroup
from app.models.homework_file import HomeworkFile
from app.models.request import UserChangeRequest
from app.models.repository import RepoBinding
from app.models.submission import AssignmentSubmission, SubmissionAsset, SubmissionMember
from app.models.user import User
from app.schemas.assignment_submission import (
    AssignmentSummary,
    ChunkFileCheckPayload,
    ChunkFileCheckResponse,
    ChunkUploadPartResponse,
    ChunkUploadSessionInfo,
    CourseInfo,
    CreateResubmitRequestPayload,
    FinalizeSubmissionResponse,
    MergeChunksPayload,
    MergeChunksResponse,
    MyHomeworkStatus,
    SubmissionAssetInfo,
    SubmissionCodeAnalysisInfo,
    SubmissionDetail,
    SubmissionMemberInfo,
    SubmissionMemberPayload,
    SubmissionSummary,
    UploadAssetResponse,
    UpsertSubmissionPayload,
)
from app.services.auth_service import get_user_by_token
from app.services.code_analysis_service import analyze_code_archive, dumps_summary, loads_summary
from app.services.file_service import (
    create_chunk_upload_session,
    finalize_chunk_upload,
    get_chunk_upload_session,
    list_chunk_upload_sessions,
    mark_chunk_upload_failed,
    remove_stored_file,
    save_chunk_upload_part,
    save_submission_asset,
)
from app.services.preview_service import PreviewError, get_preview_file
from app.services.repository_service import build_member_contribution_summary, upsert_repo_binding
from app.services.teacher_score_service import build_teacher_score_aggregate
from app.services.teacher_score_scheduler_service import enqueue_teacher_score_refresh
from app.services.workload_service import build_submission_workload_summary

router = APIRouter(tags=["submissions"])

ASSET_TYPES = {"report", "code_archive", "ppt", "video"}
_ASSET_TYPE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,48}$")


def _utcnow() -> datetime:
    return datetime.utcnow()


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    value = authorization.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return ""


def _current_user(authorization: str | None, db: Session) -> User:
    return get_user_by_token(db, _bearer_token(authorization))


def _is_admin(user: User) -> bool:
    return str(user.role or "").lower() == "admin"


def _is_teacher(user: User) -> bool:
    return str(user.role or "").lower() == "teacher"


def _ensure_student_or_admin(user: User) -> None:
    if _is_admin(user):
        return
    if _is_teacher(user):
        raise HTTPException(status_code=403, detail="students only")
    return


def _parse_required_asset_types(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _normalize_asset_type(value: str | None) -> str:
    return (value or "").strip().lower().replace(" ", "_")


def _validate_asset_type(value: str) -> None:
    if not value:
        raise HTTPException(status_code=400, detail="invalid asset_type")
    if not _ASSET_TYPE_RE.match(value):
        raise HTTPException(status_code=400, detail="invalid asset_type")


def _safe_file_name(name: str | None, fallback: str) -> str:
    raw = Path(name or fallback).name.strip()
    raw = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", raw).strip(". ")
    return raw[:240] or fallback


def _allowed_asset_types(submission: AssignmentSubmission) -> set[str] | None:
    required = {_normalize_asset_type(item) for item in _parse_required_asset_types(submission.assignment.required_asset_types)}
    required = {item for item in required if item}
    if not required:
        return None
    return required


def _assignment_summary(assignment: Assignment, my_submission: AssignmentSubmission | None = None) -> AssignmentSummary:
    return AssignmentSummary(
        id=assignment.id,
        course=CourseInfo(
            id=assignment.course.id,
            name=assignment.course.name,
            term=assignment.course.term,
        ),
        title=assignment.title,
        description=assignment.description,
        week_index=assignment.week_index,
        submission_mode=assignment.submission_mode,
        required_asset_types=_parse_required_asset_types(assignment.required_asset_types),
        due_at=assignment.due_at,
        late_due_at=assignment.late_due_at,
        status=assignment.status,
        my_submission_id=my_submission.id if my_submission else None,
        my_submission_status=my_submission.status if my_submission else None,
        my_completeness_status=my_submission.completeness_status if my_submission else None,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
    )


def _asset_info(asset: SubmissionAsset) -> SubmissionAssetInfo:
    return SubmissionAssetInfo(
        id=asset.id,
        asset_type=asset.asset_type,
        file_name=asset.file_name,
        mime_type=asset.mime_type,
        file_size=asset.file_size,
        file_hash=asset.file_hash,
        version_no=asset.version_no,
        upload_status=asset.upload_status,
        created_at=asset.created_at,
        download_url=f"/api/assets/{asset.id}/download",
    )


def _member_info(member: SubmissionMember) -> SubmissionMemberInfo:
    return SubmissionMemberInfo(
        id=member.id,
        student_name=member.student_name,
        student_id=member.student_id,
        project_role=member.project_role,
        workload_percent=member.workload_percent,
        contribution_source=member.contribution_source,
        git_author_names=member.git_author_names,
        git_author_emails=member.git_author_emails,
        personal_statement=member.personal_statement,
        created_at=member.created_at,
    )


def _latest_assets(assets: list[SubmissionAsset]) -> dict[str, SubmissionAsset]:
    latest: dict[str, SubmissionAsset] = {}
    for asset in sorted(assets, key=lambda item: (item.asset_type, item.version_no, item.created_at), reverse=True):
        latest.setdefault(asset.asset_type, asset)
    return latest


def _latest_uploaded_assets(assets: list[SubmissionAsset]) -> dict[str, SubmissionAsset]:
    latest: dict[str, SubmissionAsset] = {}
    for asset in sorted(assets, key=lambda item: (item.asset_type, item.version_no, item.created_at), reverse=True):
        if str(asset.upload_status or "").lower() != "uploaded":
            continue
        latest.setdefault(asset.asset_type, asset)
    return latest


def _submission_upload_state(submission: AssignmentSubmission | None) -> str | None:
    if not submission:
        return None
    statuses = [
        str(asset.upload_status or "uploaded").lower()
        for asset in _latest_assets(list(submission.assets or [])).values()
        if asset
    ]
    if any(status == "failed" for status in statuses):
        return "failed"
    if any(status == "uploading" for status in statuses):
        return "uploading"
    if statuses:
        return "normal"
    return None


def _has_meaningful_submission_content(submission: AssignmentSubmission | None) -> bool:
    if not submission:
        return False
    if submission.submitted_at is not None:
        return True
    if any(str(asset.upload_status or "").lower() == "uploaded" for asset in list(submission.assets or [])):
        return True
    if str(submission.statement_text or "").strip():
        return True
    if any(str(member.personal_statement or "").strip() for member in list(submission.members or [])):
        return True
    return False


def _missing_asset_types(submission: AssignmentSubmission) -> list[str]:
    required = _parse_required_asset_types(submission.assignment.required_asset_types)
    latest = _latest_uploaded_assets(submission.assets)
    missing = [asset_type for asset_type in required if asset_type not in latest]
    if not submission.members:
        missing.append("member_statements")
    else:
        valid_statements = [m for m in submission.members if (m.personal_statement or "").strip()]
        if len(valid_statements) != len(submission.members):
            missing.append("member_statements")
    if not (submission.project_name or "").strip():
        missing.append("project_name")
    return missing


def _refresh_completeness(submission: AssignmentSubmission) -> None:
    submission.completeness_status = "complete" if not _missing_asset_types(submission) else "incomplete"


def _code_analysis_info(analysis: SubmissionCodeAnalysis | None) -> SubmissionCodeAnalysisInfo | None:
    if not analysis:
        return None
    summary = loads_summary(analysis.summary_json)
    return SubmissionCodeAnalysisInfo(
        id=analysis.id,
        source_type=analysis.source_type,
        archive_format=analysis.archive_format,
        total_files=analysis.total_files,
        source_file_count=analysis.source_file_count,
        total_lines=analysis.total_lines,
        total_bytes=analysis.total_bytes,
        dominant_language=analysis.dominant_language,
        risk_level=analysis.risk_level,
        risk_flags=list(summary.get("risk_flags") or []),
        top_extensions=list(summary.get("top_extensions") or []),
        languages=dict(summary.get("languages") or {}),
        generated_at=analysis.generated_at,
    )


def _next_asset_version(submission: AssignmentSubmission, asset_type: str) -> int:
    current_versions = [asset.version_no for asset in submission.assets if asset.asset_type == asset_type]
    return (max(current_versions) if current_versions else 0) + 1


def _to_summary(db: Session, submission: AssignmentSubmission) -> SubmissionSummary:
    aggregate = build_teacher_score_aggregate(list(submission.teacher_scores or []))
    aggregate.assigned_teacher_count = len(list(submission.teacher_assignments or []))
    missing_asset_types = _missing_asset_types(submission)

    blog_risk_flags: list[str] = []
    repo_risk_flags: list[str] = []
    workload_risk_flags: list[str] = []
    teacher_risk_flags: list[str] = []

    if submission.repo_binding:
        repo_risk_flags = list((build_member_contribution_summary(submission.repo_binding) or {}).get("risk_flags") or [])
        workload_risk_flags = list((build_submission_workload_summary(submission) or {}).risk_flags or [])
    else:
        workload_risk_flags = ["no_repo_bound"]

    member_student_ids = sorted({str(item.student_id or "").strip() for item in submission.members if str(item.student_id or "").strip()})
    if member_student_ids:
        users = db.query(User).filter(User.student_id.in_(member_student_ids)).all()
        user_map = {str(item.student_id): int(item.id) for item in users}
        if user_map:
            posts = db.query(BlogPost).filter(BlogPost.user_id.in_(list(user_map.values()))).all()
            reverse_map = {int(item.id): str(item.student_id) for item in users}
            stats = {}
            for post in posts:
                sid = reverse_map.get(int(post.user_id))
                if not sid:
                    continue
                data = stats.setdefault(sid, {"post_count": 0, "code_dump_count": 0})
                data["post_count"] += 1
                data["code_dump_count"] += 1 if bool(post.is_mostly_code) or str(post.category or "") == "code_dump" else 0
            for member in submission.members:
                sid = str(member.student_id or "").strip()
                member_stats = stats.get(sid, {})
                if int(member_stats.get("post_count") or 0) == 0:
                    blog_risk_flags.append(f"blog_missing:{member.student_name}")
                if int(member_stats.get("code_dump_count") or 0) > 0:
                    blog_risk_flags.append(f"blog_code_dump:{member.student_name}")

    if aggregate.assigned_teacher_count > 0 and aggregate.score_count == 0:
        teacher_risk_flags.append("teacher_reviews_not_started")
    elif aggregate.assigned_teacher_count > 0 and aggregate.score_count < aggregate.assigned_teacher_count:
        teacher_risk_flags.append("teacher_reviews_incomplete")
    if aggregate.score_count > 0 and aggregate.average_total_score < 30:
        teacher_risk_flags.append("teacher_average_score_low")

    all_flags = []
    if missing_asset_types:
        all_flags.extend([f"missing:{item}" for item in missing_asset_types])
    all_flags.extend(blog_risk_flags)
    all_flags.extend(repo_risk_flags)
    all_flags.extend(workload_risk_flags)
    all_flags.extend(teacher_risk_flags)

    risk_level = "low"
    if missing_asset_types or blog_risk_flags or "teacher_average_score_low" in teacher_risk_flags or any(
        flag.startswith("member_without_git_activity:") for flag in repo_risk_flags
    ):
        risk_level = "high"
    elif repo_risk_flags or teacher_risk_flags or workload_risk_flags:
        risk_level = "medium"

    return SubmissionSummary(
        id=submission.id,
        assignment_id=submission.assignment_id,
        student_id=submission.student_id,
        student_name=submission.student_name,
        group_name=submission.group_name,
        project_name=submission.project_name,
        status=submission.status,
        completeness_status=submission.completeness_status,
        submitted_at=submission.submitted_at,
        upload_state=_submission_upload_state(submission),
        created_at=submission.created_at,
        updated_at=submission.updated_at,
        asset_count=len(submission.assets),
        member_count=len(submission.members),
        code_analysis=_code_analysis_info(submission.code_analysis),
        teacher_score_summary={
            "assigned_teacher_count": aggregate.assigned_teacher_count,
            "score_count": aggregate.score_count,
            "average_total_score": aggregate.average_total_score,
            "average_group_total_score": aggregate.average_group_total_score,
            "reviewed_teacher_ids": [int(item.teacher_user_id) for item in list(submission.teacher_scores or [])],
        },
        dashboard_risk_summary={
            "level": risk_level,
            "flags": all_flags,
            "missing_asset_types": missing_asset_types,
            "blog_risk_flags": blog_risk_flags,
            "repo_risk_flags": repo_risk_flags,
            "workload_risk_flags": workload_risk_flags,
            "teacher_risk_flags": teacher_risk_flags,
        },
    )


def _to_detail(db: Session, submission: AssignmentSubmission) -> SubmissionDetail:
    latest_assets = {key: _asset_info(value) for key, value in _latest_assets(submission.assets).items()}
    missing = _missing_asset_types(submission)
    base = _to_summary(db, submission)
    return SubmissionDetail(
        **base.model_dump(),
        statement_text=submission.statement_text,
        assignment=_assignment_summary(submission.assignment, submission),
        members=[_member_info(member) for member in submission.members],
        assets=[_asset_info(asset) for asset in submission.assets],
        latest_assets=latest_assets,
        missing_asset_types=missing,
    )


def _load_assignment(db: Session, assignment_id: int) -> Assignment:
    assignment = (
        db.query(Assignment)
        .options(selectinload(Assignment.course))
        .filter(Assignment.id == assignment_id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="assignment not found")
    return assignment


def _load_submission(db: Session, submission_id: int) -> AssignmentSubmission:
    submission = (
        db.query(AssignmentSubmission)
        .options(
            selectinload(AssignmentSubmission.assignment).selectinload(Assignment.course),
            selectinload(AssignmentSubmission.assets),
            selectinload(AssignmentSubmission.members),
            selectinload(AssignmentSubmission.code_analysis),
            selectinload(AssignmentSubmission.teacher_scores),
            selectinload(AssignmentSubmission.teacher_assignments),
            selectinload(AssignmentSubmission.repo_binding).selectinload(RepoBinding.commits),
        )
        .filter(AssignmentSubmission.id == submission_id)
        .first()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="submission not found")
    return submission


def _ensure_submission_access(user: User, submission: AssignmentSubmission) -> None:
    if _is_admin(user):
        return
    if getattr(submission, "group_id", None) and user.group_id and int(submission.group_id) == int(user.group_id):
        return
    member_ids = {str(m.student_id or "").strip() for m in list(submission.members or []) if str(m.student_id or "").strip()}
    if user.student_id and user.student_id in member_ids:
        return
    if submission.submitter_user_id == user.id:
        return
    raise HTTPException(status_code=403, detail="forbidden")


def _sync_members(submission: AssignmentSubmission, members: list[SubmissionMemberPayload]) -> None:
    submission.members.clear()
    for item in members:
        submission.members.append(
            SubmissionMember(
                student_name=(item.student_name or "").strip() or "unknown",
                student_id=(item.student_id or "").strip() or "unknown",
                project_role=(item.project_role or "").strip() or None,
                workload_percent=item.workload_percent,
                contribution_source=(item.contribution_source or "mixed").strip() or "mixed",
                git_author_names=(item.git_author_names or "").strip() or None,
                git_author_emails=(item.git_author_emails or "").strip() or None,
                personal_statement=(item.personal_statement or "").strip() or None,
                created_at=_utcnow(),
            )
        )


def _upsert_code_analysis(db: Session, submission: AssignmentSubmission, asset: SubmissionAsset) -> None:
    summary = analyze_code_archive(asset.file_path)
    analysis = submission.code_analysis
    if not analysis:
        analysis = SubmissionCodeAnalysis(
            submission_id=submission.id,
            asset_id=asset.id,
            source_type="code_archive",
        )
        db.add(analysis)
    analysis.asset_id = asset.id
    analysis.archive_format = str(summary.get("archive_format") or "unknown")
    analysis.total_files = int(summary.get("total_files") or 0)
    analysis.source_file_count = int(summary.get("source_file_count") or 0)
    analysis.total_lines = int(summary.get("total_lines") or 0)
    analysis.total_bytes = int(summary.get("total_bytes") or 0)
    analysis.dominant_language = summary.get("dominant_language")
    analysis.risk_level = str(summary.get("risk_level") or "unknown")
    analysis.summary_json = dumps_summary(summary)
    analysis.risk_flags_json = dumps_summary({"risk_flags": summary.get("risk_flags") or []})
    analysis.generated_at = _utcnow()


def _chunk_session_info(payload: dict | None) -> ChunkUploadSessionInfo | None:
    if not isinstance(payload, dict):
        return None
    uploaded_parts = sorted({int(item) for item in list(payload.get("uploaded_parts") or []) if int(item) >= 1})
    total_chunks = max(int(payload.get("total_chunks") or 0), 0)
    missing_parts = [idx for idx in range(1, total_chunks + 1) if idx not in uploaded_parts]
    asset_id = int(payload.get("asset_id") or 0) or None
    return ChunkUploadSessionInfo(
        upload_id=str(payload.get("upload_id") or ""),
        asset_id=asset_id,
        submission_id=int(payload.get("submission_id") or 0),
        asset_type=str(payload.get("asset_type") or ""),
        file_name=str(payload.get("file_name") or ""),
        mime_type=payload.get("mime_type"),
        file_md5=str(payload.get("file_md5") or ""),
        total_size=int(payload.get("total_size") or 0),
        total_chunks=total_chunks,
        chunk_size=int(payload.get("chunk_size") or 0),
        uploaded_parts=uploaded_parts,
        uploaded_count=len(uploaded_parts),
        missing_parts=missing_parts,
        is_complete=not missing_parts and total_chunks > 0,
        upload_status=str(payload.get("status") or "uploading"),
        error_message=(str(payload.get("error_message") or "").strip() or None),
    )


def _copy_homework_file_to_submission(
    *,
    source_path: str,
    submission_id: int,
    asset_type: str,
    version_no: int,
    file_name: str,
) -> dict[str, str | int | None]:
    source = Path(source_path)
    if not source.exists():
        raise HTTPException(status_code=404, detail="stored source file not found")
    settings = get_settings()
    safe_name = _safe_file_name(file_name, asset_type)
    suffix = Path(safe_name).suffix
    submission_dir = settings.submission_storage_path / str(submission_id) / asset_type
    submission_dir.mkdir(parents=True, exist_ok=True)
    target_path = submission_dir / f"v{version_no}_{uuid4().hex}{suffix}"
    shutil.copy2(source, target_path)
    return {
        "file_name": safe_name,
        "file_path": str(target_path),
        "file_size": int(target_path.stat().st_size),
    }


def _register_homework_file(
    db: Session,
    *,
    file_path: str,
    file_name: str,
    md5: str,
    file_size: int,
) -> None:
    normalized_md5 = str(md5 or "").strip().lower()
    if not normalized_md5:
        return
    existing = db.query(HomeworkFile).filter(HomeworkFile.md5 == normalized_md5).first()
    if existing:
        if not Path(str(existing.file_path or "")).exists():
            existing.file_path = file_path
            existing.file_name = file_name
            existing.file_size = int(file_size or 0)
        return
    db.add(
        HomeworkFile(
            file_path=file_path,
            file_name=file_name,
            md5=normalized_md5,
            file_size=int(file_size or 0),
            created_at=_utcnow(),
        )
    )


@router.get("/assignments/{assignment_id}/submissions", response_model=list[SubmissionSummary])
def list_assignment_submissions(
    assignment_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    _ensure_student_or_admin(user)
    _load_assignment(db, assignment_id)
    query = (
        db.query(AssignmentSubmission)
        .options(
            selectinload(AssignmentSubmission.assignment).selectinload(Assignment.course),
            selectinload(AssignmentSubmission.assets),
            selectinload(AssignmentSubmission.members),
            selectinload(AssignmentSubmission.code_analysis),
            selectinload(AssignmentSubmission.teacher_scores),
            selectinload(AssignmentSubmission.teacher_assignments),
            selectinload(AssignmentSubmission.repo_binding).selectinload(RepoBinding.commits),
        )
        .filter(AssignmentSubmission.assignment_id == assignment_id)
        .order_by(AssignmentSubmission.updated_at.desc())
    )
    if not _is_admin(user):
        if user.group_id:
            query = query.filter(AssignmentSubmission.group_id == user.group_id)
        else:
            query = query.filter(AssignmentSubmission.submitter_user_id == user.id)
    return [_to_summary(db, item) for item in query.all()]


@router.get("/assignments/{assignment_id}/submissions/me", response_model=SubmissionDetail | None)
def get_my_assignment_submission(
    assignment_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    _ensure_student_or_admin(user)
    _load_assignment(db, assignment_id)
    submission = (
        db.query(AssignmentSubmission)
        .options(
            selectinload(AssignmentSubmission.assignment).selectinload(Assignment.course),
            selectinload(AssignmentSubmission.assets),
            selectinload(AssignmentSubmission.members),
            selectinload(AssignmentSubmission.code_analysis),
            selectinload(AssignmentSubmission.teacher_scores),
            selectinload(AssignmentSubmission.teacher_assignments),
            selectinload(AssignmentSubmission.repo_binding).selectinload(RepoBinding.commits),
        )
        .filter(
            AssignmentSubmission.assignment_id == assignment_id,
            (AssignmentSubmission.group_id == user.group_id) if user.group_id else (AssignmentSubmission.submitter_user_id == user.id),
        )
        .first()
    )
    if not submission:
        return None
    return _to_detail(db, submission)


@router.get("/assignments/{assignment_id}/submissions/me/status", response_model=MyHomeworkStatus)
def get_my_homework_status(
    assignment_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    _ensure_student_or_admin(user)
    _load_assignment(db, assignment_id)

    if user.group_id:
        has_submission = (
            db.query(AssignmentSubmission)
            .filter(AssignmentSubmission.assignment_id == assignment_id, AssignmentSubmission.group_id == user.group_id)
            .first()
            is not None
        )
        pending = (
            db.query(UserChangeRequest)
            .filter(
                UserChangeRequest.group_id == user.group_id,
                UserChangeRequest.request_type == "homework_resubmit",
                UserChangeRequest.status == "pending",
                UserChangeRequest.assignment_id == assignment_id,
            )
            .first()
            is not None
        )
        return MyHomeworkStatus(has_submission=has_submission, pending_resubmit_request=pending)

    has_submission = (
        db.query(AssignmentSubmission)
        .filter(AssignmentSubmission.assignment_id == assignment_id, AssignmentSubmission.submitter_user_id == user.id)
        .first()
        is not None
    )
    pending = (
        db.query(UserChangeRequest)
        .filter(
            UserChangeRequest.user_id == user.id,
            UserChangeRequest.request_type == "homework_resubmit",
            UserChangeRequest.status == "pending",
            UserChangeRequest.assignment_id == assignment_id,
        )
        .first()
        is not None
    )
    return MyHomeworkStatus(has_submission=has_submission, pending_resubmit_request=pending)


def _create_homework_resubmit_request(
    assignment_id: int,
    payload: CreateResubmitRequestPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    _ensure_student_or_admin(user)
    _load_assignment(db, assignment_id)

    if not user.group_id:
        raise HTTPException(status_code=400, detail="当前账号未加入小组，无法申请重新提交作业。")

    has_submission = (
        db.query(AssignmentSubmission)
        .filter(AssignmentSubmission.assignment_id == assignment_id, AssignmentSubmission.group_id == user.group_id)
        .first()
        is not None
    )
    if not has_submission:
        raise HTTPException(status_code=400, detail="本组尚未提交该作业，无法申请重新提交。")

    pending = (
        db.query(UserChangeRequest)
        .filter(
            UserChangeRequest.group_id == user.group_id,
            UserChangeRequest.request_type == "homework_resubmit",
            UserChangeRequest.status == "pending",
            UserChangeRequest.assignment_id == assignment_id,
        )
        .first()
        is not None
    )
    if pending:
        raise HTTPException(status_code=409, detail="本组已经提交过重新提交申请，请等待管理员审核。")

    row = UserChangeRequest(
        user_id=user.id,
        group_id=user.group_id,
        assignment_id=assignment_id,
        request_type="homework_resubmit",
        status="pending",
        request_note=(payload.request_note or "").strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"message": "已提交重新提交申请，等待管理员审核。", "request_id": row.id}


@router.post("/assignments/{assignment_id}/submissions/me/resubmit-request")
def create_homework_resubmit_request(
    assignment_id: int,
    payload: CreateResubmitRequestPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    return _create_homework_resubmit_request(assignment_id, payload, authorization, db)


@router.put("/assignments/{assignment_id}/submissions/me/resubmit-request")
def create_homework_resubmit_request_put(
    assignment_id: int,
    payload: CreateResubmitRequestPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    return _create_homework_resubmit_request(assignment_id, payload, authorization, db)


@router.post("/assignments/{assignment_id}/submissions/resubmit-request")
def create_homework_resubmit_request_legacy(
    assignment_id: int,
    payload: CreateResubmitRequestPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    return _create_homework_resubmit_request(assignment_id, payload, authorization, db)


@router.put("/assignments/{assignment_id}/submissions/resubmit-request")
def create_homework_resubmit_request_legacy_put(
    assignment_id: int,
    payload: CreateResubmitRequestPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    return _create_homework_resubmit_request(assignment_id, payload, authorization, db)


@router.post("/assignments/{assignment_id}/submissions", response_model=SubmissionDetail)
def create_or_update_assignment_submission(
    assignment_id: int,
    payload: UpsertSubmissionPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    _ensure_student_or_admin(user)
    assignment = _load_assignment(db, assignment_id)
    submission = (
        db.query(AssignmentSubmission)
        .options(
            selectinload(AssignmentSubmission.assignment).selectinload(Assignment.course),
            selectinload(AssignmentSubmission.assets),
            selectinload(AssignmentSubmission.members),
            selectinload(AssignmentSubmission.code_analysis),
            selectinload(AssignmentSubmission.teacher_scores),
            selectinload(AssignmentSubmission.teacher_assignments),
            selectinload(AssignmentSubmission.repo_binding).selectinload(RepoBinding.commits),
        )
        .filter(
            AssignmentSubmission.assignment_id == assignment_id,
            (AssignmentSubmission.group_id == user.group_id) if user.group_id else (AssignmentSubmission.submitter_user_id == user.id),
        )
        .first()
    )
    if not submission:
        if user.group_id:
            group = db.query(UserGroup).filter(UserGroup.id == user.group_id).first()
            group_name = (group.name if group else "") or (payload.group_name or "")
        else:
            group_name = payload.group_name or ""
        submission = AssignmentSubmission(
            assignment_id=assignment.id,
            submitter_user_id=user.id,
            group_id=user.group_id,
            student_id=user.student_id,
            student_name=(payload.student_name or user.student_id).strip(),
            group_name=(group_name or "").strip() or None,
            project_name=(payload.project_name or "").strip() or None,
            statement_text=(payload.statement_text or "").strip() or None,
            status="draft",
            completeness_status="incomplete",
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        db.add(submission)
        db.flush()
    else:
        if not _is_admin(user) and str(submission.status or "").lower() == "submitted":
            raise HTTPException(status_code=409, detail="本组作业已提交。如需重新提交，请先点击“申请重新提交”并等待管理员审核。")
        submission.student_name = (payload.student_name or submission.student_name or user.student_id).strip()
        if user.group_id:
            group = db.query(UserGroup).filter(UserGroup.id == user.group_id).first()
            submission.group_id = user.group_id
            submission.group_name = (group.name if group else payload.group_name or submission.group_name or "").strip() or None
        else:
            submission.group_name = (payload.group_name or "").strip() or None
        submission.project_name = (payload.project_name or "").strip() or None
        submission.statement_text = (payload.statement_text or "").strip() or None
        submission.updated_at = _utcnow()

    _sync_members(submission, payload.members)
    db.flush()
    if not submission.repo_binding and user.group_id:
        group = db.query(UserGroup).filter(UserGroup.id == user.group_id).first()
        if group and group.repo_url:
            upsert_repo_binding(db, submission.id, group.repo_url)
    db.refresh(submission)
    submission.assignment = assignment
    _refresh_completeness(submission)
    db.commit()
    return _to_detail(db, _load_submission(db, submission.id))


@router.get("/submissions/{submission_id}", response_model=SubmissionDetail)
def get_submission(
    submission_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    submission = _load_submission(db, submission_id)
    _ensure_submission_access(user, submission)
    return _to_detail(db, submission)


@router.post("/submissions/{submission_id}/assets", response_model=UploadAssetResponse)
async def upload_submission_asset(
    submission_id: int,
    asset_type: str = Form(...),
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    _ensure_student_or_admin(user)
    submission = _load_submission(db, submission_id)
    _ensure_submission_access(user, submission)
    if not _is_admin(user) and str(submission.status or "").lower() == "submitted":
        raise HTTPException(status_code=409, detail="本组作业已提交，不能继续上传材料。如需重新提交，请先点击“申请重新提交”并等待管理员审核。")
    asset_type = _normalize_asset_type(asset_type)
    _validate_asset_type(asset_type)
    allowed = _allowed_asset_types(submission)
    if allowed is not None and asset_type not in allowed:
        raise HTTPException(status_code=400, detail="invalid asset_type")

    version_no = _next_asset_version(submission, asset_type)
    stored = await save_submission_asset(file, submission.id, asset_type, version_no)
    asset = SubmissionAsset(
        submission_id=submission.id,
        uploader_user_id=user.id,
        asset_type=asset_type,
        file_name=stored["file_name"],
        file_path=stored["file_path"],
        mime_type=stored["mime_type"],
        file_size=stored["file_size"],
        file_hash=stored["file_hash"],
        version_no=version_no,
        upload_status="uploaded",
        created_at=_utcnow(),
    )
    db.add(asset)
    submission.updated_at = _utcnow()
    db.flush()
    if asset_type == "code_archive":
        _upsert_code_analysis(db, submission, asset)
    db.refresh(submission)
    _refresh_completeness(submission)
    db.commit()
    detail = _to_detail(db, _load_submission(db, submission.id))
    return UploadAssetResponse(message="asset uploaded", asset=_asset_info(asset), submission=detail)


@router.post("/check_file", response_model=ChunkFileCheckResponse)
def check_file(
    payload: ChunkFileCheckPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    _ensure_student_or_admin(user)
    settings = get_settings()
    submission = _load_submission(db, payload.submission_id)
    _ensure_submission_access(user, submission)
    if not _is_admin(user) and str(submission.status or "").lower() == "submitted":
        raise HTTPException(status_code=409, detail="本组作业已提交，不能继续上传材料。如需重新提交，请先点击“申请重新提交”并等待管理员审核。")

    asset_type = _normalize_asset_type(payload.asset_type)
    _validate_asset_type(asset_type)
    allowed = _allowed_asset_types(submission)
    if allowed is not None and asset_type not in allowed:
        raise HTTPException(status_code=400, detail="invalid asset_type")

    normalized_md5 = str(payload.md5 or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{32}", normalized_md5):
        raise HTTPException(status_code=400, detail="invalid md5")
    if int(payload.file_size or 0) <= 0:
        raise HTTPException(status_code=400, detail="invalid file_size")
    if int(payload.file_size) > int(settings.upload_max_file_size_bytes):
        raise HTTPException(status_code=400, detail="file too large")

    chunk_size = int(settings.upload_chunk_size_bytes)
    total_chunks = max((int(payload.file_size) + chunk_size - 1) // chunk_size, 1)
    latest_assets = _latest_assets(list(submission.assets or []))
    current_asset = latest_assets.get(asset_type)
    if (
        current_asset
        and str(current_asset.upload_status or "").lower() == "uploaded"
        and str(current_asset.file_hash or "").strip().lower() == normalized_md5
        and int(current_asset.file_size or 0) == int(payload.file_size)
    ):
        detail = _to_detail(db, _load_submission(db, submission.id))
        return ChunkFileCheckResponse(
            exists=True,
            instant_upload=True,
            chunk_size=chunk_size,
            max_file_size=int(settings.upload_max_file_size_bytes),
            asset=_asset_info(current_asset),
            submission=detail,
        )

    indexed_file = db.query(HomeworkFile).filter(HomeworkFile.md5 == normalized_md5).first()
    if indexed_file and Path(str(indexed_file.file_path or "")).exists():
        version_no = _next_asset_version(submission, asset_type)
        stored = _copy_homework_file_to_submission(
            source_path=str(indexed_file.file_path),
            submission_id=submission.id,
            asset_type=asset_type,
            version_no=version_no,
            file_name=payload.file_name,
        )
        asset = SubmissionAsset(
            submission_id=submission.id,
            uploader_user_id=user.id,
            asset_type=asset_type,
            file_name=str(stored["file_name"]),
            file_path=str(stored["file_path"]),
            mime_type=(payload.mime_type or "").strip() or None,
            file_size=int(stored["file_size"] or payload.file_size),
            file_hash=normalized_md5,
            version_no=version_no,
            upload_status="uploaded",
            created_at=_utcnow(),
        )
        db.add(asset)
        submission.updated_at = _utcnow()
        db.flush()
        if asset_type == "code_archive":
            _upsert_code_analysis(db, submission, asset)
        _refresh_completeness(submission)
        db.commit()
        detail = _to_detail(db, _load_submission(db, submission.id))
        return ChunkFileCheckResponse(
            exists=True,
            instant_upload=True,
            chunk_size=chunk_size,
            max_file_size=int(settings.upload_max_file_size_bytes),
            asset=_asset_info(asset),
            submission=detail,
        )

    sessions = list_chunk_upload_sessions(uploader_user_id=user.id, submission_id=submission.id)
    for item in sessions:
        if str(item.get("asset_type") or "") != asset_type:
            continue
        if str(item.get("file_md5") or "").strip().lower() != normalized_md5:
            continue
        if int(item.get("total_size") or 0) != int(payload.file_size):
            continue
        existing_asset_id = int(item.get("asset_id") or 0)
        if existing_asset_id and not db.query(SubmissionAsset.id).filter(SubmissionAsset.id == existing_asset_id).first():
            continue
        session_info = _chunk_session_info(item)
        if session_info:
            return ChunkFileCheckResponse(
                exists=False,
                instant_upload=False,
                chunk_size=chunk_size,
                max_file_size=int(settings.upload_max_file_size_bytes),
                session=session_info,
            )

    version_no = _next_asset_version(submission, asset_type)
    placeholder_name = _safe_file_name(payload.file_name, asset_type)
    asset = SubmissionAsset(
        submission_id=submission.id,
        uploader_user_id=user.id,
        asset_type=asset_type,
        file_name=placeholder_name,
        file_path="",
        mime_type=(payload.mime_type or "").strip() or None,
        file_size=int(payload.file_size),
        file_hash=normalized_md5,
        version_no=version_no,
        upload_status="uploading",
        created_at=_utcnow(),
    )
    db.add(asset)
    submission.updated_at = _utcnow()
    db.flush()
    session_payload = create_chunk_upload_session(
        submission_id=submission.id,
        asset_type=asset_type,
        uploader_user_id=user.id,
        asset_id=asset.id,
        file_name=payload.file_name,
        mime_type=payload.mime_type,
        file_md5=normalized_md5,
        total_size=int(payload.file_size),
        total_chunks=total_chunks,
        chunk_size=chunk_size,
    )
    db.commit()
    return ChunkFileCheckResponse(
        exists=False,
        instant_upload=False,
        chunk_size=chunk_size,
        max_file_size=int(settings.upload_max_file_size_bytes),
        session=_chunk_session_info(session_payload),
    )


@router.post("/upload_chunk", response_model=ChunkUploadPartResponse)
async def upload_chunk(
    upload_id: str = Form(...),
    part_number: int = Form(...),
    chunk: UploadFile = File(...),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    _ensure_student_or_admin(user)
    try:
        session_payload = get_chunk_upload_session(str(upload_id).strip())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if int(session_payload.get("uploader_user_id") or 0) != int(user.id):
        raise HTTPException(status_code=403, detail="forbidden")

    submission = _load_submission(db, int(session_payload.get("submission_id") or 0))
    _ensure_submission_access(user, submission)
    if not _is_admin(user) and str(submission.status or "").lower() == "submitted":
        raise HTTPException(status_code=409, detail="本组作业已提交，不能继续上传材料。如需重新提交，请先点击“申请重新提交”并等待管理员审核。")
    asset_id = int(session_payload.get("asset_id") or 0)
    asset = db.query(SubmissionAsset).filter(SubmissionAsset.id == asset_id).first() if asset_id else None
    if not asset:
        raise HTTPException(status_code=404, detail="upload asset placeholder not found")

    try:
        data = await chunk.read()
        save_chunk_upload_part(str(upload_id).strip(), int(part_number), data)
        asset.upload_status = "uploading"
        asset.file_name = str(session_payload.get("file_name") or asset.file_name)
        asset.mime_type = session_payload.get("mime_type") or asset.mime_type
        asset.file_size = int(session_payload.get("total_size") or asset.file_size or 0)
        asset.file_hash = str(session_payload.get("file_md5") or asset.file_hash or "")
        submission.updated_at = _utcnow()
        db.commit()
        current_session = _chunk_session_info(get_chunk_upload_session(str(upload_id).strip()))
        if not current_session:
            raise HTTPException(status_code=500, detail="chunk session lost")
        return ChunkUploadPartResponse(message="chunk uploaded", session=current_session)
    except HTTPException:
        raise
    except Exception as exc:
        try:
            mark_chunk_upload_failed(str(upload_id).strip(), str(exc))
        except Exception:
            pass
        asset.upload_status = "failed"
        submission.updated_at = _utcnow()
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/merge_chunks", response_model=MergeChunksResponse)
def merge_chunks(
    payload: MergeChunksPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    _ensure_student_or_admin(user)
    upload_id = str(payload.upload_id or "").strip()
    if not upload_id:
        raise HTTPException(status_code=400, detail="upload_id required")
    try:
        session_payload = get_chunk_upload_session(upload_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if int(session_payload.get("uploader_user_id") or 0) != int(user.id):
        raise HTTPException(status_code=403, detail="forbidden")

    submission = _load_submission(db, int(session_payload.get("submission_id") or 0))
    _ensure_submission_access(user, submission)
    if not _is_admin(user) and str(submission.status or "").lower() == "submitted":
        raise HTTPException(status_code=409, detail="本组作业已提交，不能继续上传材料。如需重新提交，请先点击“申请重新提交”并等待管理员审核。")
    asset_id = int(session_payload.get("asset_id") or 0)
    asset = db.query(SubmissionAsset).filter(SubmissionAsset.id == asset_id).first() if asset_id else None
    if not asset:
        raise HTTPException(status_code=404, detail="upload asset placeholder not found")

    requested_md5 = str(payload.md5 or "").strip().lower()
    expected_md5 = str(session_payload.get("file_md5") or "").strip().lower()
    if requested_md5 and expected_md5 and requested_md5 != expected_md5:
        raise HTTPException(status_code=400, detail="md5 mismatch")

    try:
        stored = finalize_chunk_upload(upload_id, int(asset.version_no or 1))
    except Exception as exc:
        try:
            mark_chunk_upload_failed(upload_id, str(exc))
        except Exception:
            pass
        asset.upload_status = "failed"
        submission.updated_at = _utcnow()
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    asset.file_name = str(stored["file_name"])
    asset.file_path = str(stored["file_path"])
    asset.mime_type = stored.get("mime_type") or asset.mime_type
    asset.file_size = int(stored["file_size"] or 0)
    asset.file_hash = str(stored["file_hash"] or "")
    asset.upload_status = "uploaded"
    submission.updated_at = _utcnow()
    db.flush()
    _register_homework_file(
        db,
        file_path=str(stored["file_path"]),
        file_name=str(stored["file_name"]),
        md5=str(stored["file_hash"] or ""),
        file_size=int(stored["file_size"] or 0),
    )
    if asset.asset_type == "code_archive":
        _upsert_code_analysis(db, submission, asset)
    _refresh_completeness(submission)
    db.commit()
    detail = _to_detail(db, _load_submission(db, submission.id))
    return MergeChunksResponse(
        message="chunks merged",
        md5_verified=True,
        asset=_asset_info(asset),
        submission=detail,
    )


@router.delete("/assets/{asset_id}", response_model=SubmissionDetail)
def delete_submission_asset(
    asset_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    _ensure_student_or_admin(user)
    asset = db.query(SubmissionAsset).filter(SubmissionAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="asset not found")
    submission = _load_submission(db, asset.submission_id)
    _ensure_submission_access(user, submission)
    path = asset.file_path
    db.delete(asset)
    submission.updated_at = _utcnow()
    db.flush()
    if submission.code_analysis and submission.code_analysis.asset_id == asset_id:
        db.delete(submission.code_analysis)
    _refresh_completeness(submission)
    db.commit()
    remove_stored_file(path)
    return _to_detail(db, _load_submission(db, submission.id))


@router.get("/assets/{asset_id}/download")
def download_submission_asset(
    asset_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    asset = db.query(SubmissionAsset).filter(SubmissionAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="asset not found")
    submission = _load_submission(db, asset.submission_id)
    _ensure_submission_access(user, submission)
    path = Path(asset.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="stored file not found")
    return FileResponse(path=path, filename=asset.file_name)


@router.get("/assets/{asset_id}/preview")
def preview_submission_asset(
    asset_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    asset = db.query(SubmissionAsset).filter(SubmissionAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="asset not found")
    submission = _load_submission(db, asset.submission_id)
    _ensure_submission_access(user, submission)
    try:
        preview = get_preview_file(asset.file_path)
    except PreviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(path=preview.path, media_type=preview.media_type, headers={"Content-Disposition": "inline"})


@router.post("/submissions/{submission_id}/finalize", response_model=FinalizeSubmissionResponse)
def finalize_submission(
    submission_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    _ensure_student_or_admin(user)
    submission = _load_submission(db, submission_id)
    _ensure_submission_access(user, submission)
    _refresh_completeness(submission)
    missing = _missing_asset_types(submission)
    if missing:
        raise HTTPException(status_code=400, detail=f"submission incomplete: {', '.join(missing)}")
    submission.status = "submitted"
    submission.submitted_at = _utcnow()
    submission.updated_at = _utcnow()
    db.commit()
    enqueue_teacher_score_refresh(submission.id)
    detail = _to_detail(db, _load_submission(db, submission.id))
    return FinalizeSubmissionResponse(message="submission finalized", submission=detail)


@router.get("/admin/submissions", response_model=list[SubmissionSummary])
def admin_list_all_submissions(
    assignment_id: int | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="admin required")

    query = (
        db.query(AssignmentSubmission)
        .options(
            selectinload(AssignmentSubmission.assignment).selectinload(Assignment.course),
            selectinload(AssignmentSubmission.assets),
            selectinload(AssignmentSubmission.members),
            selectinload(AssignmentSubmission.code_analysis),
            selectinload(AssignmentSubmission.teacher_scores),
            selectinload(AssignmentSubmission.teacher_assignments),
            selectinload(AssignmentSubmission.repo_binding).selectinload(RepoBinding.commits),
        )
        .order_by(AssignmentSubmission.updated_at.desc())
    )
    if assignment_id:
        query = query.filter(AssignmentSubmission.assignment_id == assignment_id)
    return [
        _to_summary(db, item)
        for item in query.all()
        if _has_meaningful_submission_content(item)
    ]
