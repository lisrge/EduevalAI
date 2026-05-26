from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.base import SessionLocal
from app.models.repository import RepoBinding
from app.services.repository_service import sync_gitee_repo


@dataclass
class SchedulerRuntimeState:
    running: bool = False
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    last_result: str | None = None


_settings = get_settings()
_runtime = SchedulerRuntimeState()
_stop_event = threading.Event()
_worker_thread: threading.Thread | None = None
_sync_lock = threading.Lock()


def _current_local_time() -> datetime:
    return datetime.now()


def _week_signature(value: datetime | None) -> tuple[int, int] | None:
    if not value:
        return None
    iso = value.isocalendar()
    return iso.year, iso.week


def _is_binding_due(binding: RepoBinding, now: datetime) -> bool:
    if not bool(binding.auto_sync_enabled):
        return False
    if int(now.isoweekday()) != int(_settings.repo_auto_sync_weekday):
        return False
    if int(now.hour) < int(_settings.repo_auto_sync_hour):
        return False
    return _week_signature(binding.last_auto_sync_at) != _week_signature(now)


def run_due_repo_syncs(force: bool = False) -> dict[str, int | str]:
    if not _sync_lock.acquire(blocking=False):
        return {"bindings_scanned": 0, "bindings_synced": 0, "commits_inserted": 0, "message": "scheduler already running"}

    _runtime.running = True
    _runtime.last_run_at = _current_local_time()
    scanned = 0
    synced = 0
    commits_inserted = 0
    try:
        now = _current_local_time()
        db = SessionLocal()
        try:
            bindings = (
                db.query(RepoBinding)
                .options(selectinload(RepoBinding.submission))
                .order_by(RepoBinding.id.asc())
                .all()
            )
            for binding in bindings:
                scanned += 1
                if not force and not _is_binding_due(binding, now):
                    continue
                try:
                    inserted = sync_gitee_repo(db, binding, max_pages=int(_settings.repo_auto_sync_max_pages))
                    binding.last_auto_sync_at = now
                    db.add(binding)
                    db.commit()
                    synced += 1
                    commits_inserted += int(inserted or 0)
                except Exception as exc:
                    db.rollback()
                    binding.last_error = str(exc)
                    binding.last_auto_sync_at = now
                    db.add(binding)
                    db.commit()
            _runtime.last_success_at = _current_local_time()
            _runtime.last_result = f"scanned={scanned}, synced={synced}, commits={commits_inserted}"
            return {
                "bindings_scanned": scanned,
                "bindings_synced": synced,
                "commits_inserted": commits_inserted,
                "message": _runtime.last_result or "ok",
            }
        finally:
            db.close()
    finally:
        _runtime.running = False
        _sync_lock.release()


def get_scheduler_status() -> dict:
    return {
        "enabled": bool(_settings.repo_auto_sync_enabled),
        "poll_minutes": int(_settings.repo_auto_sync_poll_minutes),
        "weekday": int(_settings.repo_auto_sync_weekday),
        "hour": int(_settings.repo_auto_sync_hour),
        "running": bool(_runtime.running),
        "last_run_at": _runtime.last_run_at,
        "last_success_at": _runtime.last_success_at,
        "last_result": _runtime.last_result,
    }


def _worker_loop() -> None:
    interval_seconds = max(60, int(_settings.repo_auto_sync_poll_minutes) * 60)
    while not _stop_event.is_set():
        if bool(_settings.repo_auto_sync_enabled):
            try:
                run_due_repo_syncs(force=False)
            except Exception as exc:
                _runtime.last_run_at = _current_local_time()
                _runtime.last_result = f"scheduler error: {exc}"
        _stop_event.wait(interval_seconds)


def start_repo_scheduler() -> None:
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, name="repo-auto-sync", daemon=True)
    _worker_thread.start()


def stop_repo_scheduler() -> None:
    _stop_event.set()
