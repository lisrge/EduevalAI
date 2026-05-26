from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.assignment_submission import SubmissionDetail, SubmissionSummary
from app.schemas.workload import SubmissionWorkloadSummary


class TeacherScorePayload(BaseModel):
    innovation_score: int = Field(ge=0, le=10)
    completeness_score: int = Field(ge=0, le=10)
    code_quality_score: int = Field(ge=0, le=10)
    demo_score: int = Field(ge=0, le=10)
    contribution_score: int = Field(ge=0, le=10)
    comment: str | None = None


class TeacherScoreInfo(TeacherScorePayload):
    id: int
    submission_id: int
    teacher_user_id: int
    teacher_student_id: str
    total_score: int
    created_at: datetime
    updated_at: datetime


class TeacherScoreAggregate(BaseModel):
    assigned_teacher_count: int = 0
    score_count: int = 0
    average_total_score: float = 0
    average_innovation_score: float = 0
    average_completeness_score: float = 0
    average_code_quality_score: float = 0
    average_demo_score: float = 0
    average_contribution_score: float = 0


class TeacherAssigneeInfo(BaseModel):
    teacher_user_id: int
    teacher_student_id: str


class TeacherReviewQueueItem(BaseModel):
    submission: SubmissionSummary
    my_score: TeacherScoreInfo | None = None
    aggregate: TeacherScoreAggregate = Field(default_factory=TeacherScoreAggregate)
    reviewed_by_me: bool = False
    assigned_teachers: list[TeacherAssigneeInfo] = Field(default_factory=list)
    assigned_to_me: bool = False


class TeacherSubmissionReview(BaseModel):
    submission: SubmissionDetail
    workload: SubmissionWorkloadSummary
    my_score: TeacherScoreInfo | None = None
    aggregate: TeacherScoreAggregate = Field(default_factory=TeacherScoreAggregate)
    all_scores: list[TeacherScoreInfo] = Field(default_factory=list)
    assigned_teachers: list[TeacherAssigneeInfo] = Field(default_factory=list)
    assigned_to_me: bool = False


class TeacherScoreSaveResponse(BaseModel):
    message: str
    review: TeacherSubmissionReview


class TeacherAssignmentPayload(BaseModel):
    teacher_user_ids: list[int] = Field(default_factory=list)


class TeacherAssignmentUpdateResponse(BaseModel):
    message: str
    assigned_teachers: list[TeacherAssigneeInfo] = Field(default_factory=list)
    aggregate: TeacherScoreAggregate = Field(default_factory=TeacherScoreAggregate)
