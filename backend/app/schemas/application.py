from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ApplicationInfo(BaseModel):
    id: int
    group_id: int | None = None
    group_name: str = ""
    student_name: str
    student_id: str
    project_title: str
    file_name: str
    file_type: str
    file_download_url: str
    preview_url: Optional[str] = None
    score_status: str
    created_at: datetime
    updated_at: datetime


class ApplicationSummary(BaseModel):
    id: int
    group_id: int | None = None
    group_name: str = ""
    student_name: str
    student_id: str
    project_title: str
    score_status: str
    practicality_score: int | None = None
    innovation_score: int | None = None
    total_score: int | None = None
    needs_human_review: bool | None = None
    updated_at: datetime
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_download_url: Optional[str] = None
    preview_url: Optional[str] = None
    created_at: Optional[datetime] = None


class ExtractionInfo(BaseModel):
    status: str
    text_content: Optional[str] = None
    extract_error: Optional[str] = None
    text_length: int


class ScoreInfo(BaseModel):
    rubric_version: str
    model_name: str
    prompt_version: str
    practicality_score: int
    innovation_score: int
    total_score: int
    practicality_reason: Optional[str] = None
    innovation_reason: Optional[str] = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    needs_human_review: bool
    scored_at: datetime


class ApplicationDetail(BaseModel):
    application: ApplicationInfo
    extraction: ExtractionInfo
    score: Optional[ScoreInfo] = None


class MyApplicationStatus(BaseModel):
    has_application: bool
    application_reupload_allowed: bool
    pending_reupload_request: bool
    pending_signature_request: bool


class CreateUserRequestPayload(BaseModel):
    request_note: str = ""


class UserChangeRequestItem(BaseModel):
    id: int
    group_id: int | None = None
    assignment_id: int | None = None
    request_type: str
    status: str
    request_note: str = ""
    file_name: str = ""
    review_note: str = ""
    reviewed_by_admin_id: int | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AdminUserChangeRequestItem(UserChangeRequestItem):
    user_id: int
    student_id: str


class UploadResponse(BaseModel):
    message: str
    application: ApplicationInfo
    extraction: ExtractionInfo


class ScoreResponse(BaseModel):
    message: str
    application_id: int
    score: ScoreInfo


class BatchScorePayload(BaseModel):
    application_ids: list[int] = []


class BatchScoreItem(BaseModel):
    application_id: int
    success: bool
    score: Optional[ScoreInfo] = None
    error: Optional[str] = None


class BatchScoreResponse(BaseModel):
    message: str
    total_requested: int
    total_scored: int
    results: list[BatchScoreItem]


class BatchDeletePayload(BaseModel):
    application_ids: list[int]


class BatchDeleteResponse(BaseModel):
    message: str
    deleted_ids: list[int]
