from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.db.base import get_db
from app.models.course import Assignment
from app.models.repository import RepoBinding
from app.models.submission import AssignmentSubmission
from app.models.teacher_review_assignment import TeacherReviewAssignment
from app.models.teacher_score import TeacherScoreRecord
from app.models.user import User
from app.schemas.teacher_score import (
    TeacherAssignmentPayload,
    TeacherAssignmentUpdateResponse,
    TeacherReviewQueueItem,
    TeacherScorePayload,
    TeacherScoreSaveResponse,
    TeacherSubmissionReview,
)
from app.services.auth_service import get_user_by_token
from app.services.teacher_score_service import (
    build_teacher_assignment_response,
    build_teacher_review,
    build_teacher_queue_item,
    compute_total_score,
)

router = APIRouter(prefix="/teacher", tags=["teacher-scores"])


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


def _ensure_teacher_access(user: User) -> None:
    if _is_admin(user) or _is_teacher(user):
        return
    raise HTTPException(status_code=403, detail="teacher or admin required")


def _ensure_admin(user: User) -> None:
    if _is_admin(user):
        return
    raise HTTPException(status_code=403, detail="admin required")


def _is_assigned_teacher(submission: AssignmentSubmission, user_id: int) -> bool:
    assignments = list(submission.teacher_assignments or [])
    if not assignments:
        return True
    return any(int(item.teacher_user_id) == int(user_id) for item in assignments)


def _load_submission(db: Session, submission_id: int) -> AssignmentSubmission:
    submission = (
        db.query(AssignmentSubmission)
        .options(
            selectinload(AssignmentSubmission.assignment).selectinload(Assignment.course),
            selectinload(AssignmentSubmission.assets),
            selectinload(AssignmentSubmission.members),
            selectinload(AssignmentSubmission.code_analysis),
            selectinload(AssignmentSubmission.repo_binding).selectinload(RepoBinding.commits),
            selectinload(AssignmentSubmission.teacher_scores).selectinload(TeacherScoreRecord.teacher),
            selectinload(AssignmentSubmission.teacher_assignments).selectinload(TeacherReviewAssignment.teacher),
        )
        .filter(AssignmentSubmission.id == submission_id)
        .first()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="submission not found")
    return submission


def _to_submission_summary(db: Session, submission: AssignmentSubmission):
    from app.api.routes.submissions import _to_summary

    return _to_summary(db, submission)


def _to_submission_detail(db: Session, submission: AssignmentSubmission):
    from app.api.routes.submissions import _to_detail

    return _to_detail(db, submission)


@router.get("/submissions", response_model=list[TeacherReviewQueueItem])
def list_teacher_review_submissions(
    assignment_id: int | None = None,
    reviewed: str | None = None,
    scope: str | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    _ensure_teacher_access(user)

    query = (
        db.query(AssignmentSubmission)
        .options(
            selectinload(AssignmentSubmission.assignment),
            selectinload(AssignmentSubmission.assets),
            selectinload(AssignmentSubmission.members),
            selectinload(AssignmentSubmission.code_analysis),
            selectinload(AssignmentSubmission.teacher_scores).selectinload(TeacherScoreRecord.teacher),
            selectinload(AssignmentSubmission.teacher_assignments).selectinload(TeacherReviewAssignment.teacher),
        )
        .order_by(AssignmentSubmission.submitted_at.desc(), AssignmentSubmission.updated_at.desc())
        .filter(AssignmentSubmission.status == "submitted")
    )
    if assignment_id:
        _ = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        query = query.filter(AssignmentSubmission.assignment_id == assignment_id)

    items = [build_teacher_queue_item(item, user, _to_submission_summary(db, item)) for item in query.all()]
    scope_flag = str(scope or "").strip().lower()
    if _is_teacher(user) and scope_flag != "all":
        items = [item for item in items if item.assigned_to_me]
    reviewed_flag = str(reviewed or "").strip().lower()
    if reviewed_flag == "true":
        items = [item for item in items if item.reviewed_by_me]
    elif reviewed_flag == "false":
        items = [item for item in items if not item.reviewed_by_me]

    items.sort(
        key=lambda item: (
            item.reviewed_by_me,
            -int(getattr(item.submission, "member_count", 0) or 0),
            getattr(item.submission, "updated_at", datetime.min),
        )
    )
    return items


@router.get("/submissions/{submission_id}", response_model=TeacherSubmissionReview)
def get_teacher_submission_review(
    submission_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    _ensure_teacher_access(user)
    submission = _load_submission(db, submission_id)
    if _is_teacher(user) and not _is_assigned_teacher(submission, user.id):
        raise HTTPException(status_code=403, detail="submission not assigned to current teacher")
    return build_teacher_review(submission, user, _to_submission_detail(db, submission))


@router.post("/submissions/{submission_id}/score", response_model=TeacherScoreSaveResponse)
def save_teacher_submission_score(
    submission_id: int,
    payload: TeacherScorePayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    _ensure_teacher_access(user)
    submission = _load_submission(db, submission_id)
    if _is_teacher(user) and not _is_assigned_teacher(submission, user.id):
        raise HTTPException(status_code=403, detail="submission not assigned to current teacher")

    record = (
        db.query(TeacherScoreRecord)
        .filter(
            TeacherScoreRecord.submission_id == submission.id,
            TeacherScoreRecord.teacher_user_id == user.id,
        )
        .first()
    )
    if not record:
        record = TeacherScoreRecord(
            submission_id=submission.id,
            teacher_user_id=user.id,
            created_at=_utcnow(),
        )
        db.add(record)

    record.innovation_score = payload.innovation_score
    record.completeness_score = payload.completeness_score
    record.code_quality_score = payload.code_quality_score
    record.demo_score = payload.demo_score
    record.contribution_score = payload.contribution_score
    record.comment = (payload.comment or "").strip() or None
    record.total_score = compute_total_score(record)
    record.updated_at = _utcnow()
    db.commit()

    refreshed = _load_submission(db, submission.id)
    review = build_teacher_review(refreshed, user, _to_submission_detail(db, refreshed))
    return TeacherScoreSaveResponse(message="teacher score saved", review=review)


@router.get("/admin/submissions/{submission_id}/teacher-assignments", response_model=TeacherAssignmentUpdateResponse)
def get_submission_teacher_assignments(
    submission_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    _ensure_admin(user)
    submission = _load_submission(db, submission_id)
    return build_teacher_assignment_response(submission)


@router.put("/admin/submissions/{submission_id}/teacher-assignments", response_model=TeacherAssignmentUpdateResponse)
def update_submission_teacher_assignments(
    submission_id: int,
    payload: TeacherAssignmentPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    _ensure_admin(user)
    submission = _load_submission(db, submission_id)

    teacher_user_ids = sorted({int(item) for item in payload.teacher_user_ids if int(item) > 0})
    if teacher_user_ids:
        teachers = db.query(User).filter(User.id.in_(teacher_user_ids)).all()
        teacher_map = {int(item.id): item for item in teachers if str(item.role or "").lower() in {"teacher", "admin"}}
        if len(teacher_map) != len(teacher_user_ids):
            raise HTTPException(status_code=400, detail="some teachers not found or role invalid")

    submission.teacher_assignments.clear()
    for teacher_user_id in teacher_user_ids:
        submission.teacher_assignments.append(TeacherReviewAssignment(teacher_user_id=teacher_user_id))

    db.commit()
    refreshed = _load_submission(db, submission.id)
    return build_teacher_assignment_response(refreshed)
