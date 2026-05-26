from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RepoBinding(Base):
    __tablename__ = "repo_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("assignment_submissions.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(20), default="gitee", nullable=False)
    repo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    repo_owner: Mapped[str] = mapped_column(String(120), nullable=False)
    repo_name: Mapped[str] = mapped_column(String(200), nullable=False)
    default_branch: Mapped[Optional[str]] = mapped_column(String(120))
    sync_status: Mapped[str] = mapped_column(String(30), default="never_synced", nullable=False)
    auto_sync_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_auto_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    submission: Mapped["AssignmentSubmission"] = relationship(back_populates="repo_binding")
    commits: Mapped[list["RepoCommitSnapshot"]] = relationship(
        back_populates="binding",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RepoCommitSnapshot.committed_at.desc()",
    )


class RepoCommitSnapshot(Base):
    __tablename__ = "repo_commit_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    binding_id: Mapped[int] = mapped_column(ForeignKey("repo_bindings.id", ondelete="CASCADE"), index=True)
    commit_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    author_name: Mapped[Optional[str]] = mapped_column(String(120))
    author_email: Mapped[Optional[str]] = mapped_column(String(200))
    message: Mapped[Optional[str]] = mapped_column(Text)
    committed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    html_url: Mapped[Optional[str]] = mapped_column(String(500))
    additions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deletions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    changed_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    binding: Mapped[RepoBinding] = relationship(back_populates="commits")
