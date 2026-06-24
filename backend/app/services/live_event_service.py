from __future__ import annotations

import asyncio
import json
import threading
import uuid
from typing import Any

_loop: asyncio.AbstractEventLoop | None = None
_subscribers: dict[str, asyncio.Queue[str]] = {}
_lock = threading.Lock()


def configure_live_event_loop(loop: asyncio.AbstractEventLoop | None) -> None:
    global _loop
    _loop = loop


async def subscribe_live_events() -> tuple[str, asyncio.Queue[str]]:
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=20)
    subscriber_id = uuid.uuid4().hex
    with _lock:
        _subscribers[subscriber_id] = queue
    return subscriber_id, queue


def unsubscribe_live_events(subscriber_id: str) -> None:
    with _lock:
        _subscribers.pop(subscriber_id, None)


def publish_live_event(event_name: str, payload: dict[str, Any]) -> None:
    loop = _loop
    if loop is None:
        return
    message = json.dumps({
        "event": event_name,
        "payload": payload,
    }, ensure_ascii=False)
    with _lock:
        queues = list(_subscribers.values())
    for queue in queues:
        loop.call_soon_threadsafe(_push_message, queue, message)


def _push_message(queue: asyncio.Queue[str], message: str) -> None:
    if queue.full():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    try:
        queue.put_nowait(message)
    except asyncio.QueueFull:
        pass
