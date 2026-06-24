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


class RepoWeeklyMemberStat(BaseModel):
    student_name: str
    commit_count: int = 0
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    work_summary: str = ""


class RepoWeeklyStat(BaseModel):
    week_label: str
    week_start: str
    week_end: str
    commit_count: int
    active_authors: int
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    progress_status: str = "limited"
    work_summary: str = ""
    authors: list[str]
    members: list[RepoWeeklyMemberStat] = Field(default_factory=list)
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
    matched_changed_files: int = 0
    matched_weeks: list[str] = Field(default_factory=list)
    git_author_names: list[str] = Field(default_factory=list)
    git_author_emails: list[str] = Field(default_factory=list)
    has_repo_binding: bool = False


class RepoContributionSummary(BaseModel):
    members: list[RepoMemberContributionInfo]
    unmapped_authors: list[str] = Field(default_factory=list)
    non_git_members: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class RepoMemberCommitHistory(BaseModel):
    member_id: int
    student_name: str
    student_id: str
    project_role: Optional[str] = None
    commit_count: int = 0
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    commits: list[RepoCommitInfo] = Field(default_factory=list)


class RepoMemberCommitOverview(BaseModel):
    members: list[RepoMemberCommitHistory] = Field(default_factory=list)
    unmapped_commits: list[RepoCommitInfo] = Field(default_factory=list)


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


class RepoBatchSyncItem(BaseModel):
    binding_id: int
    submission_id: int
    repo_url: str
    sync_status: str
    commit_count: int = 0
    error_message: str = ""


class RepoBatchSyncResponse(BaseModel):
    total_bindings: int = 0
    success_count: int = 0
    failed_count: int = 0
    items: list[RepoBatchSyncItem] = Field(default_factory=list)


class RepoSelectedSyncPayload(BaseModel):
    submission_ids: list[int] = Field(default_factory=list)
    group_ids: list[int] = Field(default_factory=list)


class RepoMemberProgressItem(BaseModel):
    submission_id: int
    binding_id: int | None = None
    assignment_id: int | None = None
    project_name: str = ""
    group_name: str = ""
    repo_url: str = ""
    sync_status: str = "never_synced"
    last_sync_at: Optional[datetime] = None
    member_id: int
    student_name: str
    student_id: str
    project_role: Optional[str] = None
    contribution_source: str = "mixed"
    matched_commit_count: int = 0
    matched_additions: int = 0
    matched_deletions: int = 0
    matched_changed_files: int = 0
    matched_weeks: list[str] = Field(default_factory=list)
    has_repo_binding: bool = False


class RepoMemberProgressResponse(BaseModel):
    total_members: int = 0
    total_submissions: int = 0
    risk_flags: list[str] = Field(default_factory=list)
    items: list[RepoMemberProgressItem] = Field(default_factory=list)


class RepoLanguageBreakdownItem(BaseModel):
    language: str
    lines: int = 0
    percent: float = 0
    color: str = ""


class RepoCodeSummarySnapshot(BaseModel):
    archive_format: str = "zip"
    total_files: int = 0
    source_file_count: int = 0
    total_lines: int = 0
    total_bytes: int = 0
    estimated_kb: float = 0
    dominant_language: str | None = None
    risk_level: str = "unknown"
    risk_flags: list[str] = Field(default_factory=list)
    languages: list[RepoLanguageBreakdownItem] = Field(default_factory=list)


class RepoMemberWorkloadSnapshot(BaseModel):
    user_id: int | None = None
    member_id: int | None = None
    student_id: str = ""
    real_name: str = ""
    gitee_login: str = ""
    gitee_display_name: str = ""
    contribution_source: str = "mixed"
    commit_count: int = 0
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    workload_value: int = 0
    workload_percent: float = 0


class AdminUserRepoInsightResponse(BaseModel):
    user_id: int
    student_id: str
    real_name: str = ""
    group_id: int | None = None
    group_number: int | None = None
    group_name: str = ""
    project_name: str = ""
    repo_url: str = ""
    binding_id: int | None = None
    sync_status: str = "never_bound"
    last_sync_at: datetime | None = None
    analysis_generated_at: datetime | None = None
    analysis_state: str = "ready"
    analysis_stale: bool = False
    analysis_message: str = ""
    code_summary: RepoCodeSummarySnapshot = Field(default_factory=RepoCodeSummarySnapshot)
    members: list[RepoMemberWorkloadSnapshot] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
