from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BlogSourcePayload(BaseModel):
    source_url: str
    source_type: str = "personal"
    site_name: str | None = None
    is_active: bool = True


class BlogSourceInfo(BlogSourcePayload):
    id: int
    user_id: int
    last_crawled_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class BlogWorkItem(BaseModel):
    text: str


class BlogPostInfo(BaseModel):
    id: int
    user_id: int
    source_id: int | None = None
    title: str
    url: str
    status: str
    category: str
    source_type: str = "personal"
    summary_text: str = ""
    work_items: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    word_count: int = 0
    code_block_count: int = 0
    number_count: int = 0
    is_mostly_code: bool = False
    is_popular_science: bool = False
    created_at: datetime
    updated_at: datetime


class BlogPostDetail(BlogPostInfo):
    content_md: str = ""
    snapshot_hash: str | None = None


class BlogCrawlResponse(BaseModel):
    message: str
    source: BlogSourceInfo
    crawled_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    filtered_count: int = 0
    screenshot_failed_count: int = 0


class BlogOverviewItem(BaseModel):
    user_id: int
    student_id: str
    source_count: int = 0
    active_source_count: int = 0
    post_count: int = 0
    project_blog_count: int = 0
    personal_blog_count: int = 0
    code_dump_count: int = 0
    popular_science_count: int = 0
    work_item_count: int = 0
    latest_published_at: datetime | None = None
    earliest_published_at: datetime | None = None
    recent_eight_span_days: int | None = None
    scanned_blog_count: int = 0
    published_time_count: int = 0
    low_quality_count: int = 0
    filtered_popular_science_count: int = 0
    crawl_status: str = "idle"
    crawl_error: str | None = None
    risk_flags: list[str] = Field(default_factory=list)
    gitee_url: str = ""


class BlogOverviewSummary(BaseModel):
    total_sources: int = 0
    total_posts: int = 0
    total_code_dump_posts: int = 0
    total_popular_science_posts: int = 0
    total_project_blog_posts: int = 0
    incomplete_user_count: int = 0
    failed_user_count: int = 0
    burst_posting_user_count: int = 0
    users: list[BlogOverviewItem] = Field(default_factory=list)


class BlogAuditInfo(BaseModel):
    id: int
    user_id: int
    url: str
    title: str
    published_at: datetime | None = None
    classification: str
    is_project_training: bool = False
    is_mostly_code: bool = False
    is_popular_science: bool = False
    has_actual_work: bool = False
    last_seen_at: datetime
