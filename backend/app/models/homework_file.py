from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HomeworkFile(Base):
    __tablename__ = "homework_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_path: Mapped[str] = mapped_column(String(800), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    md5: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
