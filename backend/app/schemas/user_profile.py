from datetime import datetime

from pydantic import BaseModel, Field


class ProfileResponse(BaseModel):
    student_id: str
    real_name: str = ""
    created_at: datetime
    signature_file_name: str
    signature_url: str
    application_reupload_allowed: bool = False
    pending_reupload_request: bool = False
    pending_signature_request: bool = False


class ChangePasswordPayload(BaseModel):
    old_password: str
    new_password: str


class ChangePasswordResponse(BaseModel):
    message: str


class BlogCountInfo(BaseModel):
    normal: int = 0
    abnormal: int = 0


class AdminUserListItem(BaseModel):
    id: int
    student_id: str
    display_name: str = ""
    project_title: str = ""
    role: str
    is_root_admin: bool = False
    group_id: int | None = None
    group_number: int | None = None
    group_name: str = ""
    group_leader_name: str = ""
    group_project_title: str = ""
    blog: BlogCountInfo
    blog_home_url: str = ""
    blog_enabled: bool = True
    blog_crawl_status: str = "idle"
    blog_last_crawled_at: datetime | None = None
    application_reupload_allowed: bool = False
    pending_reupload_request_count: int = 0
    pending_signature_request_count: int = 0
    application_draft_count: int = 0
    task_draft_count: int = 0
    gitee_url: str = ""


class UpdateUserRolePayload(BaseModel):
    role: str


class UpdateUserRoleResponse(BaseModel):
    id: int
    role: str


class UpdateUserBasicProfilePayload(BaseModel):
    real_name: str = ""


class BlogItem(BaseModel):
    id: int
    title: str
    url: str
    status: str
    source: str = "csdn"
    summary: str = ""
    published_at: datetime | None = None
    capture_status: str = "pending"
    review_status: str = "pending"
    has_screenshot: bool = False
    has_html: bool = False
    updated_at: datetime | None = None


class UserBlogProfilePayload(BaseModel):
    blog_home_url: str | None = None
    blog_enabled: bool = True


class UserBlogProfileResponse(BaseModel):
    id: int
    student_id: str
    blog_home_url: str = ""
    blog_enabled: bool = True
    blog_crawl_status: str = "idle"
    blog_last_crawled_at: datetime | None = None


class BlogCrawlRunItem(BaseModel):
    id: int
    user_id: int
    blog_home_url: str
    status: str
    total_found: int = 0
    total_saved: int = 0
    total_failed: int = 0
    error_message: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class AdminBlogCrawlRunItem(BlogCrawlRunItem):
    student_id: str


class BatchBlogCrawlPayload(BaseModel):
    user_ids: list[int]


class BlogDetail(BaseModel):
    id: int
    user_id: int
    title: str
    url: str
    source: str = "csdn"
    summary: str = ""
    content_md: str = ""
    content_text: str = ""
    published_at: datetime | None = None
    capture_status: str = "pending"
    capture_error: str = ""
    capture_timestamp: datetime | None = None
    review_status: str = "pending"
    review_note: str = ""
    screenshot_url: str = ""
    html_url: str = ""
    content_preview_html: str = ""


class BlogReviewPayload(BaseModel):
    review_status: str
    review_note: str = ""


class BlogReviewResponse(BaseModel):
    id: int
    review_status: str
    review_note: str = ""
    reviewed_at: datetime | None = None
    reviewed_by_admin_id: int | None = None


class BlogReevaluatePayload(BaseModel):
    blog_ids: list[int]


class BlogReevaluateItem(BaseModel):
    id: int
    user_id: int
    category: str
    is_project_training: bool = False
    is_mostly_code: bool = False
    is_popular_science: bool = False
    work_item_count: int = 0


class BlogReevaluateResponse(BaseModel):
    total: int = 0
    updated: int = 0
    users: int = 0
    category_counts: dict[str, int] = Field(default_factory=dict)
    items: list[BlogReevaluateItem] = Field(default_factory=list)


class BlogUserSummaryResponse(BaseModel):
    user_id: int
    post_count: int = 0
    project_post_count: int = 0
    code_dump_count: int = 0
    popular_science_count: int = 0
    recent_eight_span_days: int | None = None
    latest_published_at: datetime | None = None
    earliest_published_at: datetime | None = None
    risk_flags: list[str] = Field(default_factory=list)
    summary_text: str = ""
    work_items: list[str] = Field(default_factory=list)


class AdminRequestReviewPayload(BaseModel):
    status: str
    review_note: str = ""


class GroupItem(BaseModel):
    id: int
    group_number: int
    name: str
    code: str
    leader_user_id: int | None = None
    leader_name: str = ""
    leader_project_title: str = ""
    member_count: int = 0
    description: str = ""
    repo_url: str | None = None


class GroupCreatePayload(BaseModel):
    group_number: int
    leader_student_id: str = ""
    description: str = ""
    repo_url: str | None = None


class GroupUpdatePayload(BaseModel):
    leader_student_id: str = ""
    description: str = ""
    repo_url: str | None = None


class GroupBootstrapPayload(BaseModel):
    total_groups: int = 86


class UserGroupAssignPayload(BaseModel):
    group_id: int | None = None


class TeacherScorePayload(BaseModel):
    score: int
    note: str = ""


class TeacherScoreResponse(BaseModel):
    student_user_id: int
    score: int
    note: str = ""
    updated_at: datetime


class TeacherStudentListItem(BaseModel):
    id: int
    student_id: str
    display_name: str = ""
    project_title: str = ""
    group_number: int | None = None
    group_name: str = ""
    blog_home_url: str = ""
    blog: BlogCountInfo
    teacher_score: int | None = None
    teacher_score_note: str = ""
    teacher_scored_at: datetime | None = None


class TeacherStudentDetail(BaseModel):
    id: int
    student_id: str
    display_name: str = ""
    project_title: str = ""
    group_number: int | None = None
    group_name: str = ""
    blog_home_url: str = ""
    blogs: list[BlogItem] = []
    work_summary: str = ""
    teacher_score: int | None = None
    teacher_score_note: str = ""
    teacher_scored_at: datetime | None = None
