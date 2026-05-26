from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.db.base import get_db
from app.models.course import Assignment
from app.models.submission import AssignmentSubmission
from app.models.user import User
from app.schemas.assignment_submission import AssignmentSummary, CourseInfo
from app.services.auth_service import get_user_by_token

router = APIRouter(prefix="/assignments", tags=["assignments"])


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    value = authorization.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return ""


def _current_user(authorization: str | None, db: Session) -> User:
    return get_user_by_token(db, _bearer_token(authorization))


def _parse_required_asset_types(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _to_summary(assignment: Assignment, my_submission: AssignmentSubmission | None) -> AssignmentSummary:
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


@router.get("", response_model=list[AssignmentSummary])
def list_assignments(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    assignments = (
        db.query(Assignment)
        .options(selectinload(Assignment.course), selectinload(Assignment.submissions))
        .order_by(Assignment.week_index.desc(), Assignment.updated_at.desc())
        .all()
    )
    result: list[AssignmentSummary] = []
    for assignment in assignments:
        my_submission = next((item for item in assignment.submissions if item.submitter_user_id == user.id), None)
        result.append(_to_summary(assignment, my_submission))
    return result


@router.get("/{assignment_id}", response_model=AssignmentSummary)
def get_assignment(
    assignment_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    assignment = (
        db.query(Assignment)
        .options(selectinload(Assignment.course), selectinload(Assignment.submissions))
        .filter(Assignment.id == assignment_id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="assignment not found")
    my_submission = next((item for item in assignment.submissions if item.submitter_user_id == user.id), None)
    return _to_summary(assignment, my_submission)
