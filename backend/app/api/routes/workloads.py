from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.db.base import get_db
from app.models.repository import RepoBinding
from app.models.submission import AssignmentSubmission
from app.models.user import User
from app.schemas.workload import SubmissionWorkloadSummary, WorkloadMemberSummary
from app.services.auth_service import get_user_by_token
from app.services.workload_service import build_submission_workload_summary

router = APIRouter(tags=["workloads"])


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
    submission = (
        db.query(AssignmentSubmission)
        .options(
            selectinload(AssignmentSubmission.members),
            selectinload(AssignmentSubmission.assets),
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
        member_ids = {str(member.student_id or "").strip() for member in submission.members}
        if str(user.student_id or "").strip() not in member_ids:
            raise HTTPException(status_code=403, detail="forbidden")


@router.get("/submissions/{submission_id}/workload", response_model=SubmissionWorkloadSummary)
def submission_workload_summary(
    submission_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    submission = _load_submission(db, submission_id)
    _ensure_submission_access(user, submission)
    return build_submission_workload_summary(submission)


@router.get("/submissions/{submission_id}/workload/{student_id}", response_model=WorkloadMemberSummary)
def submission_member_workload_summary(
    submission_id: int,
    student_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    submission = _load_submission(db, submission_id)
    _ensure_submission_access(user, submission)
    summary = build_submission_workload_summary(submission)
    for item in summary.members:
        if item.student_id == student_id:
            return item
    raise HTTPException(status_code=404, detail="student workload summary not found")
