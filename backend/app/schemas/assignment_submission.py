from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CourseInfo(BaseModel):
    id: int
    name: str
    term: Optional[str] = None


class AssignmentSummary(BaseModel):
    id: int
    course: CourseInfo
    title: str
    description: Optional[str] = None
    week_index: int
    submission_mode: str
    required_asset_types: list[str] = Field(default_factory=list)
    due_at: Optional[datetime] = None
    late_due_at: Optional[datetime] = None
    status: str
    my_submission_id: Optional[int] = None
    my_submission_status: Optional[str] = None
    my_completeness_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SubmissionMemberPayload(BaseModel):
    student_name: str
    student_id: str
    project_role: Optional[str] = None
    workload_percent: Optional[int] = None
    contribution_source: Optional[str] = "mixed"
    git_author_names: Optional[str] = None
    git_author_emails: Optional[str] = None
    personal_statement: Optional[str] = None


class SubmissionMemberInfo(SubmissionMemberPayload):
    id: int
    created_at: datetime


class SubmissionAssetInfo(BaseModel):
    id: int
    asset_type: str
    file_name: str
    mime_type: Optional[str] = None
    file_size: int
    file_hash: Optional[str] = None
    version_no: int
    upload_status: str
    created_at: datetime
    download_url: str


class SubmissionCodeAnalysisInfo(BaseModel):
    id: int
    source_type: str
    archive_format: Optional[str] = None
    total_files: int
    source_file_count: int
    total_lines: int
    total_bytes: int
    dominant_language: Optional[str] = None
    risk_level: str
    risk_flags: list[str] = Field(default_factory=list)
    top_extensions: list[dict] = Field(default_factory=list)
    languages: dict[str, int] = Field(default_factory=dict)
    generated_at: datetime


class SubmissionTeacherScoreSummary(BaseModel):
    assigned_teacher_count: int = 0
    score_count: int = 0
    average_total_score: float = 0
    reviewed_teacher_ids: list[int] = Field(default_factory=list)


class SubmissionDashboardRiskSummary(BaseModel):
    level: str = "low"
    flags: list[str] = Field(default_factory=list)
    missing_asset_types: list[str] = Field(default_factory=list)
    blog_risk_flags: list[str] = Field(default_factory=list)
    repo_risk_flags: list[str] = Field(default_factory=list)
    workload_risk_flags: list[str] = Field(default_factory=list)
    teacher_risk_flags: list[str] = Field(default_factory=list)


class SubmissionSummary(BaseModel):
    id: int
    assignment_id: int
    student_id: str
    student_name: str
    group_name: Optional[str] = None
    project_name: Optional[str] = None
    status: str
    completeness_status: str
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    asset_count: int
    member_count: int
    code_analysis: Optional[SubmissionCodeAnalysisInfo] = None
    teacher_score_summary: Optional[SubmissionTeacherScoreSummary] = None
    dashboard_risk_summary: Optional[SubmissionDashboardRiskSummary] = None


class SubmissionDetail(SubmissionSummary):
    statement_text: Optional[str] = None
    assignment: AssignmentSummary
    members: list[SubmissionMemberInfo] = Field(default_factory=list)
    assets: list[SubmissionAssetInfo] = Field(default_factory=list)
    latest_assets: dict[str, SubmissionAssetInfo] = Field(default_factory=dict)
    missing_asset_types: list[str] = Field(default_factory=list)


class UpsertSubmissionPayload(BaseModel):
    student_name: Optional[str] = None
    group_name: Optional[str] = None
    project_name: Optional[str] = None
    statement_text: Optional[str] = None
    members: list[SubmissionMemberPayload] = Field(default_factory=list)


class FinalizeSubmissionResponse(BaseModel):
    message: str
    submission: SubmissionDetail


class UploadAssetResponse(BaseModel):
    message: str
    asset: SubmissionAssetInfo
    submission: SubmissionDetail
