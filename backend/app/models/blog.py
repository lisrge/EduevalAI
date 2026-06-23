from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BlogSource(Base):
    __tablename__ = "blog_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    source_url: Mapped[str] = mapped_column(String(800), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), default="personal", nullable=False, index=True)
    site_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    posts: Mapped[list["BlogPost"]] = relationship(
        back_populates="source_row",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="BlogPost.published_at.desc()",
    )


class BlogPost(Base):
    __tablename__ = "blog_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("blog_sources.id", ondelete="SET NULL"), index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="csdn", nullable=False, index=True)
    article_uid: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="normal", nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), default="unknown", nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    work_items_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    # CSDN articles can easily exceed MySQL TEXT's 64 KiB byte limit.
    content_md: Mapped[str] = mapped_column(Text().with_variant(LONGTEXT(), "mysql"), default="", nullable=False)
    content_text: Mapped[str] = mapped_column(Text().with_variant(LONGTEXT(), "mysql"), default="", nullable=False)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    raw_html_path: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    screenshot_path: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    code_block_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    number_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_mostly_code: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_popular_science: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    capture_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    capture_error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    capture_timestamp: Mapped[datetime | None] = mapped_column(DateTime)
    review_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    review_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_by_admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    source_row: Mapped[BlogSource | None] = relationship(back_populates="posts")


class BlogCrawlRun(Base):
    __tablename__ = "blog_crawl_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    blog_home_url: Mapped[str] = mapped_column(String(800), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="queued", nullable=False, index=True)
    triggered_by_admin_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    total_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_saved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BlogAuditItem(Base):
    __tablename__ = "blog_audit_items"
    __table_args__ = (UniqueConstraint("user_id", "url", name="ux_blog_audit_user_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("blog_crawl_runs.id", ondelete="SET NULL"), index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    classification: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False, index=True)
    is_project_training: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_mostly_code: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_popular_science: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    has_actual_work: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
