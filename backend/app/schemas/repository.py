from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RepoBindingPayload(BaseModel):
    repo_url: str
    default_branch: Optional[str] = None


class RepoAutoSyncPayload(BaseModel):
    auto_sync_enabled: bool = True


class RepoBindingInfo(BaseModel):
    id: int
    submission_id: int
    platform: str
    repo_url: str
    repo_owner: str
    repo_name: str
    default_branch: Optional[str] = None
    sync_status: str
    auto_sync_enabled: bool
    last_sync_at: Optional[datetime] = None
    last_auto_sync_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class RepoCommitInfo(BaseModel):
    id: int
    commit_hash: str
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    message: Optional[str] = None
    committed_at: datetime
    html_url: Optional[str] = None
    additions: int
    deletions: int
    changed_files: int


class RepoWeeklyStat(BaseModel):
    week_label: str
    week_start: str
    week_end: str
    commit_count: int
    active_authors: int
    authors: list[str]
    mapped_students: list[str] = Field(default_factory=list)
    unmapped_authors: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class RepoMemberMappingPayload(BaseModel):
    member_id: int
    contribution_source: str = "mixed"
    git_author_names: Optional[str] = None
    git_author_emails: Optional[str] = None


class RepoMemberMappingUpdatePayload(BaseModel):
    members: list[RepoMemberMappingPayload]


class RepoMemberContributionInfo(BaseModel):
    member_id: int
    student_name: str
    student_id: str
    project_role: Optional[str] = None
    contribution_source: str
    matched_commit_count: int
    matched_additions: int
    matched_deletions: int
    matched_weeks: list[str] = Field(default_factory=list)
    git_author_names: list[str] = Field(default_factory=list)
    git_author_emails: list[str] = Field(default_factory=list)
    has_repo_binding: bool = False


class RepoContributionSummary(BaseModel):
    members: list[RepoMemberContributionInfo]
    unmapped_authors: list[str] = Field(default_factory=list)
    non_git_members: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class RepoSyncResponse(BaseModel):
    message: str
    binding: RepoBindingInfo
    commit_count: int


class RepoAutoSyncSchedulerStatus(BaseModel):
    enabled: bool
    poll_minutes: int
    weekday: int
    hour: int
    running: bool
    last_run_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_result: Optional[str] = None
