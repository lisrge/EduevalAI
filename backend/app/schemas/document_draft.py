from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class DraftSummary(BaseModel):
    id: int
    group_id: int | None = None
    title: str
    status: str
    created_at: datetime
    updated_at: datetime


class DraftDetail(DraftSummary):
    content: dict[str, Any]


class DraftCreatePayload(BaseModel):
    title: Optional[str] = None
    content: Optional[dict[str, Any]] = None


class DraftUpdatePayload(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    content: Optional[dict[str, Any]] = None
