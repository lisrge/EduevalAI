from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AssignmentSubmission(Base):
    __tablename__ = "assignment_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"), index=True)
    submitter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    student_name: Mapped[str] = mapped_column(String(100), default="unknown", nullable=False)
    group_name: Mapped[Optional[str]] = mapped_column(String(200))
    project_name: Mapped[Optional[str]] = mapped_column(String(255))
    statement_text: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    completeness_status: Mapped[str] = mapped_column(String(30), default="incomplete", nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assignment: Mapped["Assignment"] = relationship(back_populates="submissions")
    assets: Mapped[list["SubmissionAsset"]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SubmissionAsset.created_at.desc()",
    )
    members: Mapped[list["SubmissionMember"]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SubmissionMember.id.asc()",
    )
    code_analysis: Mapped[Optional["SubmissionCodeAnalysis"]] = relationship(
        back_populates="submission",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    repo_binding: Mapped[Optional["RepoBinding"]] = relationship(
        back_populates="submission",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    teacher_scores: Mapped[list["TeacherScoreRecord"]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TeacherScoreRecord.updated_at.desc()",
    )
    teacher_assignments: Mapped[list["TeacherReviewAssignment"]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TeacherReviewAssignment.created_at.asc()",
    )


class SubmissionMember(Base):
    __tablename__ = "submission_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("assignment_submissions.id", ondelete="CASCADE"), index=True)
    student_name: Mapped[str] = mapped_column(String(100), nullable=False)
    student_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    project_role: Mapped[Optional[str]] = mapped_column(String(120))
    workload_percent: Mapped[Optional[int]] = mapped_column(Integer)
    contribution_source: Mapped[str] = mapped_column(String(20), default="mixed", nullable=False)
    git_author_names: Mapped[Optional[str]] = mapped_column(String(500))
    git_author_emails: Mapped[Optional[str]] = mapped_column(String(500))
    personal_statement: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    submission: Mapped[AssignmentSubmission] = relationship(back_populates="members")


class SubmissionAsset(Base):
    __tablename__ = "submission_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("assignment_submissions.id", ondelete="CASCADE"), index=True)
    uploader_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    asset_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(800), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(120))
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    upload_status: Mapped[str] = mapped_column(String(30), default="uploaded", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    submission: Mapped[AssignmentSubmission] = relationship(back_populates="assets")
