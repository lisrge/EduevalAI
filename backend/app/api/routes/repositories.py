from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.db.base import get_db
from app.models.repository import RepoBinding, RepoCommitSnapshot
from app.models.submission import AssignmentSubmission
from app.models.user import User
from app.schemas.repository import (
    RepoAutoSyncPayload,
    RepoAutoSyncSchedulerStatus,
    RepoBindingInfo,
    RepoBindingPayload,
    RepoCommitInfo,
    RepoContributionSummary,
    RepoMemberMappingUpdatePayload,
    RepoSyncResponse,
    RepoWeeklyStat,
)
from app.services.auth_service import get_user_by_token
from app.services.repo_scheduler_service import get_scheduler_status, run_due_repo_syncs
from app.services.repository_service import (
    build_member_contribution_summary,
    build_weekly_stats,
    sync_gitee_repo,
    upsert_repo_binding,
)

router = APIRouter(tags=["repositories"])


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


def _load_submission(db: Session, submission_id: int) -> AssignmentSubmission:
    submission = db.query(AssignmentSubmission).filter(AssignmentSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="submission not found")
    return submission


def _ensure_submission_access(user: User, submission: AssignmentSubmission) -> None:
    if _is_admin(user):
        return
    if submission.submitter_user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")


def _binding_info(binding: RepoBinding) -> RepoBindingInfo:
    return RepoBindingInfo(
        id=binding.id,
        submission_id=binding.submission_id,
        platform=binding.platform,
        repo_url=binding.repo_url,
        repo_owner=binding.repo_owner,
        repo_name=binding.repo_name,
        default_branch=binding.default_branch,
        sync_status=binding.sync_status,
        auto_sync_enabled=bool(binding.auto_sync_enabled),
        last_sync_at=binding.last_sync_at,
        last_auto_sync_at=binding.last_auto_sync_at,
        last_error=binding.last_error,
        created_at=binding.created_at,
        updated_at=binding.updated_at,
    )


def _commit_info(commit: RepoCommitSnapshot) -> RepoCommitInfo:
    return RepoCommitInfo(
        id=commit.id,
        commit_hash=commit.commit_hash,
        author_name=commit.author_name,
        author_email=commit.author_email,
        message=commit.message,
        committed_at=commit.committed_at,
        html_url=commit.html_url,
        additions=commit.additions,
        deletions=commit.deletions,
        changed_files=commit.changed_files,
    )


@router.post("/submissions/{submission_id}/repo-binding", response_model=RepoBindingInfo)
def upsert_submission_repo_binding(
    submission_id: int,
    payload: RepoBindingPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    submission = _load_submission(db, submission_id)
    _ensure_submission_access(user, submission)
    binding = upsert_repo_binding(db, submission_id, payload.repo_url, payload.default_branch)
    return _binding_info(binding)


@router.get("/submissions/{submission_id}/repo-binding", response_model=RepoBindingInfo | None)
def get_submission_repo_binding(
    submission_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    submission = _load_submission(db, submission_id)
    _ensure_submission_access(user, submission)
    binding = db.query(RepoBinding).filter(RepoBinding.submission_id == submission_id).first()
    if not binding:
        return None
    return _binding_info(binding)


@router.post("/repo-bindings/{binding_id}/sync", response_model=RepoSyncResponse)
def sync_repo_binding_now(
    binding_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    binding = (
        db.query(RepoBinding)
        .options(selectinload(RepoBinding.submission))
        .filter(RepoBinding.id == binding_id)
        .first()
    )
    if not binding:
        raise HTTPException(status_code=404, detail="repo binding not found")
    _ensure_submission_access(user, binding.submission)
    inserted = sync_gitee_repo(db, binding)
    return RepoSyncResponse(message="repo sync completed", binding=_binding_info(binding), commit_count=inserted)


@router.put("/repo-bindings/{binding_id}/auto-sync", response_model=RepoBindingInfo)
def update_repo_binding_auto_sync(
    binding_id: int,
    payload: RepoAutoSyncPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    binding = (
        db.query(RepoBinding)
        .options(selectinload(RepoBinding.submission))
        .filter(RepoBinding.id == binding_id)
        .first()
    )
    if not binding:
        raise HTTPException(status_code=404, detail="repo binding not found")
    _ensure_submission_access(user, binding.submission)
    binding.auto_sync_enabled = bool(payload.auto_sync_enabled)
    db.add(binding)
    db.commit()
    db.refresh(binding)
    return _binding_info(binding)


@router.get("/repo-sync/scheduler-status", response_model=RepoAutoSyncSchedulerStatus)
def repo_scheduler_status(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="admin required")
    return RepoAutoSyncSchedulerStatus(**get_scheduler_status())


@router.post("/repo-sync/run-now", response_model=dict)
def run_repo_scheduler_now(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="admin required")
    return run_due_repo_syncs(force=True)


@router.get("/repo-bindings/{binding_id}/commits", response_model=list[RepoCommitInfo])
def list_repo_commits(
    binding_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    binding = (
        db.query(RepoBinding)
        .options(selectinload(RepoBinding.submission), selectinload(RepoBinding.commits))
        .filter(RepoBinding.id == binding_id)
        .first()
    )
    if not binding:
        raise HTTPException(status_code=404, detail="repo binding not found")
    _ensure_submission_access(user, binding.submission)
    return [_commit_info(item) for item in binding.commits]


@router.get("/repo-bindings/{binding_id}/weekly-stats", response_model=list[RepoWeeklyStat])
def repo_weekly_stats(
    binding_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    binding = (
        db.query(RepoBinding)
        .options(selectinload(RepoBinding.submission), selectinload(RepoBinding.commits))
        .filter(RepoBinding.id == binding_id)
        .first()
    )
    if not binding:
        raise HTTPException(status_code=404, detail="repo binding not found")
    _ensure_submission_access(user, binding.submission)
    return [RepoWeeklyStat(**item) for item in build_weekly_stats(binding)]


@router.post("/submissions/{submission_id}/repo-member-mappings", response_model=RepoContributionSummary)
def update_repo_member_mappings(
    submission_id: int,
    payload: RepoMemberMappingUpdatePayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    submission = (
        db.query(AssignmentSubmission)
        .options(
            selectinload(AssignmentSubmission.members),
            selectinload(AssignmentSubmission.repo_binding).selectinload(RepoBinding.commits),
        )
        .filter(AssignmentSubmission.id == submission_id)
        .first()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="submission not found")
    _ensure_submission_access(user, submission)
    member_map = {member.id: member for member in submission.members}
    for item in payload.members:
        member = member_map.get(item.member_id)
        if not member:
            raise HTTPException(status_code=404, detail=f"member not found: {item.member_id}")
        member.contribution_source = (item.contribution_source or "mixed").strip() or "mixed"
        member.git_author_names = (item.git_author_names or "").strip() or None
        member.git_author_emails = (item.git_author_emails or "").strip() or None
    db.commit()
    db.refresh(submission)
    if not submission.repo_binding:
        return RepoContributionSummary(members=[], unmapped_authors=[], non_git_members=[], risk_flags=[])
    summary = build_member_contribution_summary(submission.repo_binding)
    return RepoContributionSummary(
        members=summary["members"],
        unmapped_authors=summary["unmapped_authors"],
        non_git_members=summary["non_git_members"],
        risk_flags=summary["risk_flags"],
    )


@router.get("/submissions/{submission_id}/repo-contributions", response_model=RepoContributionSummary)
def submission_repo_contributions(
    submission_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    submission = (
        db.query(AssignmentSubmission)
        .options(
            selectinload(AssignmentSubmission.members),
            selectinload(AssignmentSubmission.repo_binding).selectinload(RepoBinding.commits),
        )
        .filter(AssignmentSubmission.id == submission_id)
        .first()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="submission not found")
    _ensure_submission_access(user, submission)
    if not submission.repo_binding:
        members = [
            {
                "member_id": member.id,
                "student_name": member.student_name,
                "student_id": member.student_id,
                "project_role": member.project_role,
                "contribution_source": member.contribution_source or "mixed",
                "matched_commit_count": 0,
                "matched_additions": 0,
                "matched_deletions": 0,
                "matched_weeks": [],
                "git_author_names": [],
                "git_author_emails": [],
                "has_repo_binding": False,
            }
            for member in submission.members
        ]
        non_git_members = [
            member.student_name for member in submission.members if (member.contribution_source or "mixed") == "non_git"
        ]
        risk_flags = ["no_repo_bound"] if not non_git_members else ["no_repo_bound", "non_git_members_present"]
        return RepoContributionSummary(
            members=members,
            unmapped_authors=[],
            non_git_members=non_git_members,
            risk_flags=risk_flags,
        )
    summary = build_member_contribution_summary(submission.repo_binding)
    return RepoContributionSummary(
        members=summary["members"],
        unmapped_authors=summary["unmapped_authors"],
        non_git_members=summary["non_git_members"],
        risk_flags=summary["risk_flags"],
    )
