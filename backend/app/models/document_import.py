from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentImportBatch(Base):
    __tablename__ = "document_import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="parsed", nullable=False, index=True)
    group_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    committed_group_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime)

    files: Mapped[list["DocumentImportFile"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", passive_deletes=True
    )


class DocumentImportFile(Base):
    __tablename__ = "document_import_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("document_import_batches.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("user_groups.id", ondelete="SET NULL"), index=True)
    document_type: Mapped[str] = mapped_column(String(30), default="unknown", nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    parse_status: Mapped[str] = mapped_column(String(30), default="parsed", nullable=False, index=True)
    parse_error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    group_key: Mapped[str] = mapped_column(String(128), default="", nullable=False, index=True)
    parsed_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    batch: Mapped[DocumentImportBatch] = relationship(back_populates="files")
