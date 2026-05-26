from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ApplicationRecord(Base):
    __tablename__ = "application_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uploader_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user_groups.id", ondelete="SET NULL"), index=True)
    student_name: Mapped[str] = mapped_column(String(100), default="unknown")
    student_id: Mapped[str] = mapped_column(String(50), default="unknown", index=True)
    project_title: Mapped[str] = mapped_column(String(255), default="unknown")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(800), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)

    text_extract_status: Mapped[str] = mapped_column(String(30), default="uploaded")
    text_content: Mapped[Optional[str]] = mapped_column(Text)
    extract_error: Mapped[Optional[str]] = mapped_column(Text)

    score_status: Mapped[str] = mapped_column(String(30), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    score_result: Mapped[Optional["ScoreResult"]] = relationship(
        back_populates="application",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ScoreResult(Base):
    __tablename__ = "score_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("application_records.id", ondelete="CASCADE"), unique=True)

    rubric_version: Mapped[str] = mapped_column(String(50), default="v1.0")
    model_name: Mapped[str] = mapped_column(String(100), default="heuristic")
    prompt_version: Mapped[str] = mapped_column(String(50), default="v1.0")

    practicality_score: Mapped[int] = mapped_column(Integer, default=0)
    innovation_score: Mapped[int] = mapped_column(Integer, default=0)
    total_score: Mapped[int] = mapped_column(Integer, default=0)

    practicality_reason: Mapped[Optional[str]] = mapped_column(Text)
    innovation_reason: Mapped[Optional[str]] = mapped_column(Text)
    strengths: Mapped[Optional[str]] = mapped_column(Text)
    weaknesses: Mapped[Optional[str]] = mapped_column(Text)

    needs_human_review: Mapped[bool] = mapped_column(Boolean, default=True)
    scored_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application: Mapped[ApplicationRecord] = relationship(back_populates="score_result")
