from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, selectinload

from app.db.base import get_db
from app.models.application import ApplicationRecord
from app.models.course import Assignment
from app.models.repository import RepoBinding
from app.models.submission import AssignmentSubmission
from app.models.teacher_review_assignment import TeacherReviewAssignment
from app.models.teacher_score import TeacherScoreRecord
from app.models.user import User
from app.services.auth_service import get_user_by_token
from app.services.export_service import (
    build_csv_bytes,
    build_teacher_score_csv_bytes,
    build_teacher_score_xlsx_bytes,
    build_xlsx_bytes,
)
from app.services.teacher_score_service import build_teacher_score_aggregate

router = APIRouter(prefix="/exports", tags=["exports"])


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    value = authorization.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return ""


def _current_user(authorization: str | None, db: Session) -> User:
    return get_user_by_token(db, _bearer_token(authorization))


def _require_admin(user: User) -> None:
    if str(user.role or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="admin required")


@router.get("/scores")
def export_scores(format: str = Query("csv", pattern="^(csv|xlsx)$"), db: Session = Depends(get_db)):
    records = db.query(ApplicationRecord).order_by(ApplicationRecord.id.asc()).all()
    rows: list[dict] = []
    for record in records:
        score = record.score_result
        rows.append(
            {
                "id": record.id,
                "student_name": record.student_name,
                "student_id": record.student_id,
                "project_title": record.project_title,
                "practicality_score": score.practicality_score if score else 0,
                "innovation_score": score.innovation_score if score else 0,
                "total_score": score.total_score if score else 0,
                "needs_human_review": score.needs_human_review if score else True,
            }
        )

    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    if format == "csv":
        content = build_csv_bytes(rows)
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="scores_{stamp}.csv"'},
        )
    if format == "xlsx":
        content = build_xlsx_bytes(rows)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="scores_{stamp}.xlsx"'},
        )

    raise HTTPException(status_code=400, detail="unsupported format")


@router.get("/teacher-scores")
def export_teacher_scores(
    format: str = Query("xlsx", pattern="^(csv|xlsx)$"),
    assignment_id: int | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    me = _current_user(authorization, db)
    _require_admin(me)

    query = (
        db.query(AssignmentSubmission)
        .options(
            selectinload(AssignmentSubmission.assignment).selectinload(Assignment.course),
            selectinload(AssignmentSubmission.repo_binding).selectinload(RepoBinding.commits),
            selectinload(AssignmentSubmission.teacher_scores).selectinload(TeacherScoreRecord.teacher),
            selectinload(AssignmentSubmission.teacher_assignments).selectinload(TeacherReviewAssignment.teacher),
        )
        .order_by(AssignmentSubmission.updated_at.desc())
    )
    if assignment_id:
        query = query.filter(AssignmentSubmission.assignment_id == assignment_id)
    submissions = query.all()

    summary_rows: list[dict] = []
    score_rows: list[dict] = []

    for submission in submissions:
        assignment = submission.assignment
        course = getattr(assignment, "course", None) if assignment else None
        course_name = getattr(course, "name", "") if course else ""
        assignment_title = getattr(assignment, "title", "") if assignment else ""

        records = list(submission.teacher_scores or [])
        assignees = list(submission.teacher_assignments or [])
        assigned_teacher_ids = [int(item.teacher_user_id) for item in assignees]
        assigned_teacher_id_set = set(assigned_teacher_ids)

        aggregate = build_teacher_score_aggregate(records)
        aggregate.assigned_teacher_count = len(assigned_teacher_id_set)

        summary_rows.append(
            {
                "submission_id": submission.id,
                "assignment_id": submission.assignment_id,
                "course_name": course_name,
                "assignment_title": assignment_title,
                "student_id": submission.student_id,
                "student_name": submission.student_name,
                "group_name": submission.group_name,
                "project_name": submission.project_name,
                "status": submission.status,
                "completeness_status": submission.completeness_status,
                "assigned_teacher_count": aggregate.assigned_teacher_count,
                "score_count": aggregate.score_count,
                "average_total_score": aggregate.average_total_score,
                "average_innovation_score": aggregate.average_innovation_score,
                "average_completeness_score": aggregate.average_completeness_score,
                "average_code_quality_score": aggregate.average_code_quality_score,
                "average_demo_score": aggregate.average_demo_score,
                "average_contribution_score": aggregate.average_contribution_score,
                "updated_at": submission.updated_at,
            }
        )

        score_map = {int(item.teacher_user_id): item for item in records}
        if assignees:
            for assignee in assignees:
                teacher = getattr(assignee, "teacher", None)
                teacher_role = getattr(teacher, "role", None) if teacher else None
                record = score_map.get(int(assignee.teacher_user_id))
                score_rows.append(
                    {
                        "submission_id": submission.id,
                        "assignment_id": submission.assignment_id,
                        "course_name": course_name,
                        "assignment_title": assignment_title,
                        "student_id": submission.student_id,
                        "student_name": submission.student_name,
                        "group_name": submission.group_name,
                        "project_name": submission.project_name,
                        "teacher_student_id": getattr(teacher, "student_id", "") if teacher else "",
                        "teacher_role": str(teacher_role or ""),
                        "assigned": True,
                        "scored": record is not None,
                        "innovation_score": getattr(record, "innovation_score", None) if record else None,
                        "completeness_score": getattr(record, "completeness_score", None) if record else None,
                        "code_quality_score": getattr(record, "code_quality_score", None) if record else None,
                        "demo_score": getattr(record, "demo_score", None) if record else None,
                        "contribution_score": getattr(record, "contribution_score", None) if record else None,
                        "total_score": getattr(record, "total_score", None) if record else None,
                        "comment": getattr(record, "comment", None) if record else None,
                        "updated_at": getattr(record, "updated_at", None) if record else None,
                    }
                )
        else:
            for record in records:
                teacher = getattr(record, "teacher", None)
                teacher_role = getattr(teacher, "role", None) if teacher else None
                score_rows.append(
                    {
                        "submission_id": submission.id,
                        "assignment_id": submission.assignment_id,
                        "course_name": course_name,
                        "assignment_title": assignment_title,
                        "student_id": submission.student_id,
                        "student_name": submission.student_name,
                        "group_name": submission.group_name,
                        "project_name": submission.project_name,
                        "teacher_student_id": getattr(teacher, "student_id", "") if teacher else "",
                        "teacher_role": str(teacher_role or ""),
                        "assigned": True,
                        "scored": True,
                        "innovation_score": record.innovation_score,
                        "completeness_score": record.completeness_score,
                        "code_quality_score": record.code_quality_score,
                        "demo_score": record.demo_score,
                        "contribution_score": record.contribution_score,
                        "total_score": record.total_score,
                        "comment": record.comment,
                        "updated_at": record.updated_at,
                    }
                )

    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    if format == "csv":
        content = build_teacher_score_csv_bytes(score_rows)
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="teacher_scores_{stamp}.csv"'},
        )
    if format == "xlsx":
        content = build_teacher_score_xlsx_bytes(summary_rows, score_rows)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="teacher_scores_{stamp}.xlsx"'},
        )

    raise HTTPException(status_code=400, detail="unsupported format")
