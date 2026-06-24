from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.assignment_submission import SubmissionDetail, SubmissionSummary
from app.schemas.workload import SubmissionWorkloadSummary
from app.schemas.blog import BlogPostInfo


class MemberBlogSummary(BaseModel):
    student_id: str
    student_name: str
    blog_count: int
    low_quality_count: int
    blogs: list[BlogPostInfo] = Field(default_factory=list)


class SubmissionBlogSummary(BaseModel):
    total_blog_count: int = 0
    total_low_quality_count: int = 0
    member_blogs: list[MemberBlogSummary] = Field(default_factory=list)


class TeacherMemberBlogItem(BaseModel):
    id: int
    title: str
    url: str
    status: str
    category: str
    summary_text: str = ""
    published_at: datetime | None = None
    word_count: int = 0
    is_mostly_code: bool = False
    created_at: datetime
    updated_at: datetime


class TeacherMemberBlogListResponse(BaseModel):
    submission_id: int
    student_id: str
    student_name: str
    project_name: str | None = None
    group_name: str | None = None
    total_blog_count: int = 0
    blogs: list[TeacherMemberBlogItem] = Field(default_factory=list)


class TeacherMemberScorePayload(BaseModel):
    student_id: str
    personal_work_difficulty_score: int = Field(ge=0, le=100)
    live_demo_score: int = Field(ge=0, le=100, default=100)
    comment: str | None = None


class TeacherScorePayload(BaseModel):
    project_display_score: int = Field(ge=0, le=100)
    project_innovation_score: int = Field(ge=0, le=100)
    key_highlight_score: int = Field(ge=0, le=100)
    member_scores: list[TeacherMemberScorePayload] = Field(default_factory=list)
    comment: str | None = None


class TeacherMemberScoreInfo(TeacherMemberScorePayload):
    student_name: str = ""
    personal_total_score: float = 0
    final_score: float = 0


class TeacherMemberAggregateInfo(BaseModel):
    student_id: str
    student_name: str = ""
    score_count: int = 0
    average_personal_score: float = 0
    capped_final_score: float = 0
    five_scale_score: int = 0


class TeacherScoreInfo(TeacherScorePayload):
    id: int
    submission_id: int
    teacher_user_id: int
    teacher_student_id: str
    group_total_score: float = 0
    total_score: float
    created_at: datetime
    updated_at: datetime


class TeacherGroupScoreRecommendation(BaseModel):
    project_display_score: int = 0
    project_innovation_score: int = 0
    key_highlight_score: int = 0
    group_total_score: float = 0
    reason: str = ""


class TeacherMemberScoreRecommendation(BaseModel):
    student_id: str
    student_name: str = ""
    personal_work_difficulty_score: int = 0
    live_demo_score: int = 100
    personal_total_score: float = 0
    final_score: float = 0
    reason: str = ""


class TeacherScoreRecommendation(BaseModel):
    source_model: str = ""
    generated_at: datetime | None = None
    needs_human_review: bool = False
    overview: str = ""
    group: TeacherGroupScoreRecommendation = Field(default_factory=TeacherGroupScoreRecommendation)
    members: list[TeacherMemberScoreRecommendation] = Field(default_factory=list)


class TeacherScoreAggregate(BaseModel):
    assigned_teacher_count: int = 0
    score_count: int = 0
    average_total_score: float = 0
    average_group_total_score: float = 0
    average_project_display_score: float = 0
    average_project_innovation_score: float = 0
    average_key_highlight_score: float = 0
    average_member_personal_score: float = 0
    average_five_scale_score: float = 0


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
    blog_summary: SubmissionBlogSummary = Field(default_factory=SubmissionBlogSummary)
    my_score: TeacherScoreInfo | None = None
    ai_recommendation: TeacherScoreRecommendation = Field(default_factory=TeacherScoreRecommendation)
    aggregate: TeacherScoreAggregate = Field(default_factory=TeacherScoreAggregate)
    member_aggregates: list[TeacherMemberAggregateInfo] = Field(default_factory=list)
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
