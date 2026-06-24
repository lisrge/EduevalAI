from __future__ import annotations

import asyncio

from fastapi import APIRouter, Header, Query
from fastapi.responses import StreamingResponse

from app.db.base import SessionLocal
from app.services.auth_service import get_user_by_token
from app.services.live_event_service import subscribe_live_events, unsubscribe_live_events

router = APIRouter(prefix="/events", tags=["events"])


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    value = authorization.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return ""


def _current_user(authorization: str | None, access_token: str | None):
    token = (access_token or "").strip() or _bearer_token(authorization)
    db = SessionLocal()
    try:
        return get_user_by_token(db, token)
    finally:
        db.close()


@router.get("/stream")
async def stream_live_events(
    authorization: str | None = Header(default=None),
    access_token: str | None = Query(default=None),
):
    _current_user(authorization, access_token)
    subscriber_id, queue = await subscribe_live_events()

    async def event_generator():
        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=20)
                    yield f"data: {message}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            unsubscribe_live_events(subscriber_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
