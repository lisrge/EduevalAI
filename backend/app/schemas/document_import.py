from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ImportedMember(BaseModel):
    student_id: str = Field(pattern=r"^\d{12}$")
    name: str = ""
    blog_url: str = ""
    role: str = ""


class ImportedGroupPreview(BaseModel):
    group_key: str
    project_name: str
    team_name: str = ""
    leader_name: str = ""
    leader_student_id: str = ""
    gitee_url: str = ""
    members: list[ImportedMember] = Field(default_factory=list)
    application_file_ids: list[int] = Field(default_factory=list)
    task_file_ids: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DocumentImportFileInfo(BaseModel):
    id: int
    document_type: str
    file_name: str
    parse_status: str
    parse_error: str = ""


class DocumentImportPreviewResponse(BaseModel):
    batch_id: int
    status: str
    files: list[DocumentImportFileInfo]
    groups: list[ImportedGroupPreview]
    created_at: datetime


class ImportedCredential(BaseModel):
    student_id: str
    real_name: str
    initial_password: str


class DocumentImportCommitResponse(BaseModel):
    batch_id: int
    created_group_count: int = 0
    updated_group_count: int = 0
    duplicate_group_count: int = 0
    credentials: list[ImportedCredential] = Field(default_factory=list)


class DocumentImportCommitPayload(BaseModel):
    groups: list[ImportedGroupPreview] = Field(default_factory=list)
