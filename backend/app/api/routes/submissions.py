from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from app.db.base import get_db
from app.models.blog import BlogPost
from app.models.code_analysis import SubmissionCodeAnalysis
from app.models.course import Assignment
from app.models.repository import RepoBinding
from app.models.submission import AssignmentSubmission, SubmissionAsset, SubmissionMember
from app.models.user import User
from app.schemas.assignment_submission import (
    AssignmentSummary,
    CourseInfo,
    FinalizeSubmissionResponse,
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
from app.services.file_service import remove_stored_file, save_submission_asset
from app.services.repository_service import build_member_contribution_summary
from app.services.teacher_score_service import build_teacher_score_aggregate
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


def _missing_asset_types(submission: AssignmentSubmission) -> list[str]:
    required = _parse_required_asset_types(submission.assignment.required_asset_types)
    latest = _latest_assets(submission.assets)
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
        created_at=submission.created_at,
        updated_at=submission.updated_at,
        asset_count=len(submission.assets),
        member_count=len(submission.members),
        code_analysis=_code_analysis_info(submission.code_analysis),
        teacher_score_summary={
            "assigned_teacher_count": aggregate.assigned_teacher_count,
            "score_count": aggregate.score_count,
            "average_total_score": aggregate.average_total_score,
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
    if submission.submitter_user_id != user.id:
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
        .filter(AssignmentSubmission.assignment_id == assignment_id, AssignmentSubmission.submitter_user_id == user.id)
        .first()
    )
    if not submission:
        return None
    return _to_detail(db, submission)


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
        .filter(AssignmentSubmission.assignment_id == assignment_id, AssignmentSubmission.submitter_user_id == user.id)
        .first()
    )
    if not submission:
        submission = AssignmentSubmission(
            assignment_id=assignment.id,
            submitter_user_id=user.id,
            student_id=user.student_id,
            student_name=(payload.student_name or user.student_id).strip(),
            group_name=(payload.group_name or "").strip() or None,
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
        submission.student_name = (payload.student_name or submission.student_name or user.student_id).strip()
        submission.group_name = (payload.group_name or "").strip() or None
        submission.project_name = (payload.project_name or "").strip() or None
        submission.statement_text = (payload.statement_text or "").strip() or None
        submission.updated_at = _utcnow()

    _sync_members(submission, payload.members)
    db.flush()
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
    return [_to_summary(db, item) for item in query.all()]
