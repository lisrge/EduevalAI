from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.db.base import get_db
from app.models.course import Assignment
from app.models.gitee_profile import UserGiteeProfile
from app.models.group import UserGroup
from app.models.repository import RepoBinding, RepoCommitSnapshot
from app.models.submission import AssignmentSubmission, SubmissionMember
from app.models.user import User
from app.schemas.repository import (
    AdminUserRepoInsightResponse,
    RepoAutoSyncPayload,
    RepoAutoSyncSchedulerStatus,
    RepoBatchSyncItem,
    RepoBatchSyncResponse,
    RepoBindingInfo,
    RepoBindingPayload,
    RepoCommitInfo,
    RepoContributionSummary,
    RepoMemberProgressItem,
    RepoMemberProgressResponse,
    RepoMemberMappingUpdatePayload,
    RepoMemberCommitHistory,
    RepoMemberCommitOverview,
    RepoSelectedSyncPayload,
    RepoSyncResponse,
    RepoWeeklyStat,
)
from app.services.auth_service import get_user_by_token
from app.services.repo_scheduler_service import (
    enqueue_repo_preload,
    get_repo_preload_state,
    get_scheduler_status,
    run_due_repo_syncs,
)
from app.services.repository_service import (
    build_member_contribution_summary,
    build_member_commit_histories,
    build_weekly_stats,
    load_cached_repo_insight_snapshot,
    parse_gitee_repo_url,
    repo_insight_needs_refresh,
    sync_gitee_repo,
    upsert_repo_binding,
)

router = APIRouter(tags=["repositories"])


def _latest_group_assignment(db: Session) -> Assignment | None:
    return (
        db.query(Assignment)
        .filter(Assignment.submission_mode == "group")
        .order_by(Assignment.week_index.desc(), Assignment.id.desc())
        .first()
    )


def _ensure_group_submission_binding(db: Session, group: UserGroup) -> RepoBinding | None:
    repo_url = str(group.repo_url or "").strip()
    if not repo_url:
        return None
    parse_gitee_repo_url(repo_url)

    assignment = _latest_group_assignment(db)
    if not assignment:
        raise HTTPException(status_code=400, detail="no group assignment found")

    members = db.query(User).filter(User.group_id == group.id).order_by(User.id.asc()).all()
    if not members:
        raise HTTPException(status_code=400, detail=f"group {group.id} has no members")

    leader = next((item for item in members if item.id == group.leader_user_id), None) or members[0]
    submission = (
        db.query(AssignmentSubmission)
        .options(selectinload(AssignmentSubmission.members), selectinload(AssignmentSubmission.repo_binding))
        .filter(
            AssignmentSubmission.assignment_id == assignment.id,
            AssignmentSubmission.group_name == group.name,
        )
        .first()
    )

    if not submission:
        submission = AssignmentSubmission(
            assignment_id=assignment.id,
            submitter_user_id=leader.id,
            student_id=leader.student_id,
            student_name=leader.real_name or leader.student_id,
            group_name=group.name,
            project_name=group.description or group.name,
            status="draft",
            completeness_status="incomplete",
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)

    existing_members = {str(item.student_id): item for item in (submission.members or [])}
    changed = False
    for member_user in members:
        if str(member_user.student_id) in existing_members:
            continue
        submission.members.append(
            SubmissionMember(
                student_name=member_user.real_name or member_user.student_id,
                student_id=member_user.student_id,
                contribution_source="mixed",
            )
        )
        changed = True
    if changed:
        db.add(submission)
        db.commit()
        db.refresh(submission)

    return upsert_repo_binding(db, submission.id, repo_url)


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


def _admin_user_repo_insight_payload(db: Session, user: User, refresh: bool = False) -> AdminUserRepoInsightResponse:
    group = db.query(UserGroup).filter(UserGroup.id == user.group_id).first() if user.group_id else None
    if not group:
        return AdminUserRepoInsightResponse(
            user_id=user.id,
            student_id=user.student_id,
            real_name=user.real_name or "",
            group_id=None,
            group_number=None,
            group_name="",
            project_name="",
            repo_url="",
            binding_id=None,
            sync_status="no_group",
            analysis_state="missing",
            analysis_stale=False,
            analysis_message="",
            code_summary={},
            members=[],
            risk_flags=["user_without_group"],
        )

    binding = None
    submission = None
    if str(group.repo_url or "").strip():
        binding = _ensure_group_submission_binding(db, group)
        submission = (
            db.query(AssignmentSubmission)
            .options(
                selectinload(AssignmentSubmission.members),
                selectinload(AssignmentSubmission.repo_binding).selectinload(RepoBinding.commits),
            )
            .filter(AssignmentSubmission.id == binding.submission_id)
            .first()
            if binding
            else None
        )
        if submission and submission.repo_binding:
            binding = submission.repo_binding
    analysis_payload = None
    analysis_state = "missing"
    analysis_stale = False
    analysis_message = ""
    if binding:
        analysis_payload = load_cached_repo_insight_snapshot(binding)
        analysis_stale = repo_insight_needs_refresh(binding, analysis_payload)
        if refresh or analysis_stale:
            enqueue_repo_preload(binding.id, force=bool(refresh))
        preload_state = get_repo_preload_state(binding.id)
        if analysis_payload:
            analysis_state = preload_state if preload_state != "idle" else "ready"
        else:
            analysis_state = preload_state if preload_state != "idle" else "missing"
        if refresh:
            analysis_message = "已提交后台刷新任务，页面会自动更新。"
        elif not analysis_payload and binding:
            analysis_message = "仓库分析正在后台预加载，请稍后查看。"
        elif analysis_stale:
            analysis_message = "当前先展示最近一次缓存结果，后台正在刷新最新仓库分析。"

    if not analysis_payload:
        analysis_payload = {
            "binding_id": binding.id if binding else None,
            "repo_url": str(group.repo_url or ""),
            "sync_status": str(binding.sync_status if binding else "never_bound"),
            "last_sync_at": binding.last_sync_at.isoformat() if binding and binding.last_sync_at else None,
            "analysis_generated_at": None,
            "code_summary": {},
            "members": [
                {
                    "user_id": item.id,
                    "member_id": None,
                    "student_id": item.student_id,
                    "real_name": item.real_name or item.student_id,
                    "gitee_login": "",
                    "gitee_display_name": "",
                    "contribution_source": "mixed",
                    "commit_count": 0,
                    "additions": 0,
                    "deletions": 0,
                    "changed_files": 0,
                    "workload_value": 0,
                    "workload_percent": 0.0,
                }
                for item in db.query(User).filter(User.group_id == group.id).order_by(User.id.asc()).all()
            ],
            "risk_flags": ["analysis_pending" if binding else "no_repo_bound"],
        }
    return AdminUserRepoInsightResponse(
        user_id=user.id,
        student_id=user.student_id,
        real_name=user.real_name or "",
        group_id=group.id,
        group_number=group.group_number,
        group_name=group.name or "",
        project_name=(submission.project_name if submission else group.description) or "",
        repo_url=str(group.repo_url or ""),
        binding_id=analysis_payload.get("binding_id"),
        sync_status=str(analysis_payload.get("sync_status") or "never_bound"),
        last_sync_at=datetime.fromisoformat(analysis_payload["last_sync_at"]) if analysis_payload.get("last_sync_at") else None,
        analysis_generated_at=(
            datetime.fromisoformat(analysis_payload["analysis_generated_at"])
            if analysis_payload.get("analysis_generated_at")
            else None
        ),
        analysis_state=analysis_state,
        analysis_stale=bool(analysis_stale),
        analysis_message=analysis_message,
        code_summary=analysis_payload.get("code_summary") or {},
        members=analysis_payload.get("members") or [],
        risk_flags=analysis_payload.get("risk_flags") or [],
    )


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
    enqueue_repo_preload(binding.id, force=True)
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
    enqueue_repo_preload(binding.id, force=True)
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


@router.post("/repo-sync/run-all-bindings", response_model=RepoBatchSyncResponse)
def run_all_repo_bindings_now(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="admin required")

    groups = (
        db.query(UserGroup)
        .filter(UserGroup.repo_url.isnot(None), UserGroup.repo_url != "")
        .order_by(UserGroup.id.asc())
        .all()
    )
    items: list[RepoBatchSyncItem] = []
    success_count = 0
    failed_count = 0

    for group in groups:
        try:
            _ensure_group_submission_binding(db, group)
        except HTTPException as exc:
            failed_count += 1
            items.append(
                RepoBatchSyncItem(
                    binding_id=0,
                    submission_id=0,
                    repo_url=str(group.repo_url or ""),
                    sync_status="invalid_group_repo",
                    commit_count=0,
                    error_message=f"group {group.id}: {str(exc.detail or '')}",
                )
            )

    bindings = db.query(RepoBinding).options(selectinload(RepoBinding.submission)).order_by(RepoBinding.id.asc()).all()

    for binding in bindings:
        try:
            inserted = sync_gitee_repo(db, binding)
            success_count += 1
            items.append(
                RepoBatchSyncItem(
                    binding_id=binding.id,
                    submission_id=binding.submission_id,
                    repo_url=binding.repo_url,
                    sync_status=binding.sync_status,
                    commit_count=inserted,
                    error_message="",
                )
            )
        except HTTPException as exc:
            failed_count += 1
            items.append(
                RepoBatchSyncItem(
                    binding_id=binding.id,
                    submission_id=binding.submission_id,
                    repo_url=binding.repo_url,
                    sync_status=binding.sync_status,
                    commit_count=0,
                    error_message=str(exc.detail or ""),
                )
            )

    return RepoBatchSyncResponse(
        total_bindings=len(bindings) + len([item for item in items if item.binding_id == 0]),
        success_count=success_count,
        failed_count=failed_count,
        items=items,
    )


@router.post("/repo-sync/run-selected-bindings", response_model=RepoBatchSyncResponse)
def run_selected_repo_bindings_now(
    payload: RepoSelectedSyncPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="admin required")

    submission_ids = {int(item) for item in (payload.submission_ids or []) if item}
    group_ids = sorted({int(item) for item in (payload.group_ids or []) if item})

    items: list[RepoBatchSyncItem] = []
    success_count = 0
    failed_count = 0

    if group_ids:
        groups = db.query(UserGroup).filter(UserGroup.id.in_(group_ids)).order_by(UserGroup.id.asc()).all()
        for group in groups:
            try:
                binding = _ensure_group_submission_binding(db, group)
                if binding:
                    submission_ids.add(int(binding.submission_id))
            except HTTPException as exc:
                failed_count += 1
                items.append(
                    RepoBatchSyncItem(
                        binding_id=0,
                        submission_id=0,
                        repo_url=str(group.repo_url or ""),
                        sync_status="invalid_group_repo",
                        commit_count=0,
                        error_message=f"group {group.id}: {str(exc.detail or '')}",
                    )
                )

    submission_ids = sorted(submission_ids)
    if not submission_ids:
        return RepoBatchSyncResponse(
            total_bindings=len(items),
            success_count=success_count,
            failed_count=failed_count,
            items=items,
        )

    bindings = (
        db.query(RepoBinding)
        .options(selectinload(RepoBinding.submission))
        .filter(RepoBinding.submission_id.in_(submission_ids))
        .order_by(RepoBinding.id.asc())
        .all()
    )

    for binding in bindings:
        try:
            inserted = sync_gitee_repo(db, binding)
            success_count += 1
            items.append(
                RepoBatchSyncItem(
                    binding_id=binding.id,
                    submission_id=binding.submission_id,
                    repo_url=binding.repo_url,
                    sync_status=binding.sync_status,
                    commit_count=inserted,
                    error_message="",
                )
            )
        except HTTPException as exc:
            failed_count += 1
            items.append(
                RepoBatchSyncItem(
                    binding_id=binding.id,
                    submission_id=binding.submission_id,
                    repo_url=binding.repo_url,
                    sync_status=binding.sync_status,
                    commit_count=0,
                    error_message=str(exc.detail or ""),
                )
            )

    return RepoBatchSyncResponse(
        total_bindings=len(bindings) + len([item for item in items if item.binding_id == 0]),
        success_count=success_count,
        failed_count=failed_count,
        items=items,
    )


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


@router.get("/repo-bindings/{binding_id}/member-commits", response_model=RepoMemberCommitOverview)
def list_repo_member_commits(
    binding_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    binding = (
        db.query(RepoBinding)
        .options(
            selectinload(RepoBinding.submission).selectinload(AssignmentSubmission.members),
            selectinload(RepoBinding.commits),
        )
        .filter(RepoBinding.id == binding_id)
        .first()
    )
    if not binding:
        raise HTTPException(status_code=404, detail="repo binding not found")
    _ensure_submission_access(user, binding.submission)
    payload = build_member_commit_histories(binding)
    return RepoMemberCommitOverview(
        members=[
            RepoMemberCommitHistory(
                **{key: value for key, value in item.items() if key != "commits"},
                commits=[_commit_info(commit) for commit in item["commits"]],
            )
            for item in payload["members"]
        ],
        unmapped_commits=[_commit_info(commit) for commit in payload["unmapped_commits"]],
    )


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
    enqueue_repo_preload(submission.repo_binding.id, force=True)
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


@router.get("/repo-sync/member-progress", response_model=RepoMemberProgressResponse)
def admin_repo_member_progress(
    authorization: str | None = Header(default=None),
    assignment_id: int | None = None,
    submission_id: int | None = None,
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="admin required")

    query = db.query(AssignmentSubmission).options(
        selectinload(AssignmentSubmission.members),
        selectinload(AssignmentSubmission.repo_binding).selectinload(RepoBinding.commits),
    )
    if assignment_id is not None:
        query = query.filter(AssignmentSubmission.assignment_id == assignment_id)
    if submission_id is not None:
        query = query.filter(AssignmentSubmission.id == submission_id)
    submissions = query.order_by(AssignmentSubmission.id.asc()).all()

    items: list[RepoMemberProgressItem] = []
    risk_flags: set[str] = set()
    for submission in submissions:
        binding = submission.repo_binding
        if not binding:
            for member in submission.members:
                items.append(
                    RepoMemberProgressItem(
                        submission_id=submission.id,
                        binding_id=None,
                        assignment_id=submission.assignment_id,
                        project_name=submission.project_name or "",
                        group_name=submission.group_name or "",
                        repo_url="",
                        sync_status="never_bound",
                        last_sync_at=None,
                        member_id=member.id,
                        student_name=member.student_name,
                        student_id=member.student_id,
                        project_role=member.project_role,
                        contribution_source=member.contribution_source or "mixed",
                        matched_commit_count=0,
                        matched_additions=0,
                        matched_deletions=0,
                        matched_changed_files=0,
                        matched_weeks=[],
                        has_repo_binding=False,
                    )
                )
            risk_flags.add(f"submission_without_repo:{submission.id}")
            continue

        summary = build_member_contribution_summary(binding)
        for flag in summary.get("risk_flags") or []:
            risk_flags.add(f"{submission.id}:{flag}")
        for member in summary.get("members") or []:
            items.append(
                RepoMemberProgressItem(
                    submission_id=submission.id,
                    binding_id=binding.id,
                    assignment_id=submission.assignment_id,
                    project_name=submission.project_name or "",
                    group_name=submission.group_name or "",
                    repo_url=binding.repo_url,
                    sync_status=binding.sync_status,
                    last_sync_at=binding.last_sync_at,
                    member_id=member["member_id"],
                    student_name=member["student_name"],
                    student_id=member["student_id"],
                    project_role=member.get("project_role"),
                    contribution_source=member.get("contribution_source") or "mixed",
                    matched_commit_count=int(member.get("matched_commit_count") or 0),
                    matched_additions=int(member.get("matched_additions") or 0),
                    matched_deletions=int(member.get("matched_deletions") or 0),
                    matched_changed_files=int(member.get("matched_changed_files") or 0),
                    matched_weeks=list(member.get("matched_weeks") or []),
                    has_repo_binding=bool(member.get("has_repo_binding")),
                )
            )

    return RepoMemberProgressResponse(
        total_members=len(items),
        total_submissions=len(submissions),
        risk_flags=sorted(risk_flags),
        items=items,
    )


@router.get("/admin/users/{user_id}/repo-insight", response_model=AdminUserRepoInsightResponse)
def admin_user_repo_insight(
    user_id: int,
    refresh: bool = False,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="admin required")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    return _admin_user_repo_insight_payload(db, target, refresh=refresh)
