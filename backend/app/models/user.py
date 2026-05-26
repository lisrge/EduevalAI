from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[str] = mapped_column(String(12), unique=True, index=True, nullable=False)
    real_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    password_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False, index=True)
    is_root_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user_groups.id", ondelete="SET NULL"), index=True)
    blog_home_url: Mapped[Optional[str]] = mapped_column(String(800))
    blog_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    blog_crawl_status: Mapped[str] = mapped_column(String(30), default="idle", nullable=False, index=True)
    blog_last_crawled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    application_reupload_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    signature_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    signature_path: Mapped[str] = mapped_column(String(800), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    user: Mapped[User] = relationship(back_populates="sessions")


class TeacherScore(Base):
    __tablename__ = "teacher_scores"
    __table_args__ = (UniqueConstraint("teacher_user_id", "student_user_id", name="ux_teacher_scores_teacher_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    teacher_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    student_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
