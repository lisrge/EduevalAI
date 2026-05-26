from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TeacherReviewAssignment(Base):
    __tablename__ = "teacher_review_assignments"
    __table_args__ = (
        UniqueConstraint("submission_id", "teacher_user_id", name="ux_teacher_review_assignment"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("assignment_submissions.id", ondelete="CASCADE"), index=True)
    teacher_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    submission: Mapped["AssignmentSubmission"] = relationship(back_populates="teacher_assignments")
    teacher: Mapped["User"] = relationship()
