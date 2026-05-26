from __future__ import annotations

from app.models.submission import AssignmentSubmission
from app.models.teacher_review_assignment import TeacherReviewAssignment
from app.models.teacher_score import TeacherScoreRecord
from app.models.user import User
from app.schemas.teacher_score import (
    TeacherAssigneeInfo,
    TeacherAssignmentUpdateResponse,
    TeacherReviewQueueItem,
    TeacherScoreAggregate,
    TeacherScoreInfo,
    TeacherSubmissionReview,
)
from app.schemas.workload import SubmissionWorkloadSummary
from app.services.workload_service import build_submission_workload_summary


def compute_total_score(record: TeacherScoreRecord) -> int:
    return int(
        (record.innovation_score or 0)
        + (record.completeness_score or 0)
        + (record.code_quality_score or 0)
        + (record.demo_score or 0)
        + (record.contribution_score or 0)
    )


def to_teacher_score_info(record: TeacherScoreRecord) -> TeacherScoreInfo:
    teacher = getattr(record, "teacher", None)
    return TeacherScoreInfo(
        id=record.id,
        submission_id=record.submission_id,
        teacher_user_id=record.teacher_user_id,
        teacher_student_id=getattr(teacher, "student_id", "") or "",
        innovation_score=record.innovation_score,
        completeness_score=record.completeness_score,
        code_quality_score=record.code_quality_score,
        demo_score=record.demo_score,
        contribution_score=record.contribution_score,
        comment=record.comment,
        total_score=record.total_score,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def build_teacher_score_aggregate(records: list[TeacherScoreRecord]) -> TeacherScoreAggregate:
    if not records:
        return TeacherScoreAggregate()

    count = len(records)
    return TeacherScoreAggregate(
        assigned_teacher_count=0,
        score_count=count,
        average_total_score=round(sum(int(item.total_score or 0) for item in records) / count, 2),
        average_innovation_score=round(sum(int(item.innovation_score or 0) for item in records) / count, 2),
        average_completeness_score=round(sum(int(item.completeness_score or 0) for item in records) / count, 2),
        average_code_quality_score=round(sum(int(item.code_quality_score or 0) for item in records) / count, 2),
        average_demo_score=round(sum(int(item.demo_score or 0) for item in records) / count, 2),
        average_contribution_score=round(sum(int(item.contribution_score or 0) for item in records) / count, 2),
    )


def find_my_teacher_score(records: list[TeacherScoreRecord], user_id: int) -> TeacherScoreRecord | None:
    for item in records:
        if int(item.teacher_user_id) == int(user_id):
            return item
    return None


def build_assignee_info(records: list[TeacherReviewAssignment]) -> list[TeacherAssigneeInfo]:
    items: list[TeacherAssigneeInfo] = []
    for record in records:
        teacher = getattr(record, "teacher", None)
        if not teacher:
            continue
        items.append(
            TeacherAssigneeInfo(
                teacher_user_id=record.teacher_user_id,
                teacher_student_id=teacher.student_id,
            )
        )
    return items


def build_teacher_review(
    submission: AssignmentSubmission,
    my_user: User,
    submission_detail,
) -> TeacherSubmissionReview:
    records = list(submission.teacher_scores or [])
    assignees = list(submission.teacher_assignments or [])
    my_score = find_my_teacher_score(records, my_user.id)
    assigned_teacher_ids = {item.teacher_user_id for item in assignees}
    aggregate = build_teacher_score_aggregate(records)
    aggregate.assigned_teacher_count = len(assigned_teacher_ids)
    workload: SubmissionWorkloadSummary = build_submission_workload_summary(submission)
    return TeacherSubmissionReview(
        submission=submission_detail,
        workload=workload,
        my_score=to_teacher_score_info(my_score) if my_score else None,
        aggregate=aggregate,
        all_scores=[to_teacher_score_info(item) for item in records],
        assigned_teachers=build_assignee_info(assignees),
        assigned_to_me=(not assignees) or (my_user.id in assigned_teacher_ids),
    )


def build_teacher_queue_item(
    submission: AssignmentSubmission,
    my_user: User,
    submission_summary,
) -> TeacherReviewQueueItem:
    records = list(submission.teacher_scores or [])
    assignees = list(submission.teacher_assignments or [])
    my_score = find_my_teacher_score(records, my_user.id)
    assigned_teacher_ids = {item.teacher_user_id for item in assignees}
    aggregate = build_teacher_score_aggregate(records)
    aggregate.assigned_teacher_count = len(assigned_teacher_ids)
    return TeacherReviewQueueItem(
        submission=submission_summary,
        my_score=to_teacher_score_info(my_score) if my_score else None,
        aggregate=aggregate,
        reviewed_by_me=my_score is not None,
        assigned_teachers=build_assignee_info(assignees),
        assigned_to_me=(not assignees) or (my_user.id in assigned_teacher_ids),
    )


def build_teacher_assignment_response(submission: AssignmentSubmission) -> TeacherAssignmentUpdateResponse:
    aggregate = build_teacher_score_aggregate(list(submission.teacher_scores or []))
    aggregate.assigned_teacher_count = len(list(submission.teacher_assignments or []))
    return TeacherAssignmentUpdateResponse(
        message="teacher assignments updated",
        assigned_teachers=build_assignee_info(list(submission.teacher_assignments or [])),
        aggregate=aggregate,
    )
