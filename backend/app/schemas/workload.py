from __future__ import annotations

from pydantic import BaseModel, Field


class WorkloadEvidenceItem(BaseModel):
    label: str
    value: str


class WorkloadMemberSummary(BaseModel):
    member_id: int
    student_name: str
    student_id: str
    project_role: str | None = None
    contribution_source: str
    workload_index: int
    rank_order: int
    declared_workload_percent: int | None = None
    blog_post_count: int = 0
    blog_code_dump_count: int = 0
    blog_popular_science_count: int = 0
    blog_work_item_count: int = 0
    summary_text: str
    evidence: list[WorkloadEvidenceItem] = Field(default_factory=list)


class SubmissionWorkloadSummary(BaseModel):
    submission_id: int
    project_name: str | None = None
    group_name: str | None = None
    has_repo_binding: bool
    risk_flags: list[str] = Field(default_factory=list)
    total_blog_posts: int = 0
    members: list[WorkloadMemberSummary] = Field(default_factory=list)
