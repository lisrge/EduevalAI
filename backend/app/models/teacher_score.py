from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TeacherScoreRecord(Base):
    __tablename__ = "teacher_score_records"
    __table_args__ = (
        UniqueConstraint("submission_id", "teacher_user_id", name="ux_teacher_score_submission_teacher"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("assignment_submissions.id", ondelete="CASCADE"), index=True)
    teacher_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Legacy columns kept mapped so inserts remain compatible with old MySQL schemas.
    innovation_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completeness_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    code_quality_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    demo_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    contribution_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    project_display_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    project_innovation_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    key_highlight_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    group_total_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    member_scores_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    total_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    submission: Mapped["AssignmentSubmission"] = relationship(back_populates="teacher_scores")
    teacher: Mapped["User"] = relationship()
