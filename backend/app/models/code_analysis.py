from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SubmissionCodeAnalysis(Base):
    __tablename__ = "submission_code_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("assignment_submissions.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("submission_assets.id", ondelete="SET NULL"), index=True)
    source_type: Mapped[str] = mapped_column(String(40), default="code_archive", nullable=False)
    archive_format: Mapped[Optional[str]] = mapped_column(String(20))
    total_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_file_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_lines: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dominant_language: Mapped[Optional[str]] = mapped_column(String(50))
    risk_level: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    risk_flags_json: Mapped[Optional[str]] = mapped_column(Text)
    summary_json: Mapped[Optional[str]] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    submission: Mapped["AssignmentSubmission"] = relationship(back_populates="code_analysis")
