from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.base import SessionLocal
from app.models.repository import RepoBinding
from app.models.submission import AssignmentSubmission
from app.services.repository_service import (
    build_repo_insight_snapshot,
    load_cached_repo_insight_snapshot,
    repo_insight_needs_refresh,
    sync_gitee_repo,
)


@dataclass
class SchedulerRuntimeState:
    running: bool = False
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    last_result: str | None = None


_settings = get_settings()
_runtime = SchedulerRuntimeState()
_stop_event = threading.Event()
_wake_event = threading.Event()
_worker_thread: threading.Thread | None = None
_sync_lock = threading.Lock()
_queue_lock = threading.Lock()
_pending_binding_requests: dict[int, bool] = {}
_active_binding_ids: set[int] = set()


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


def _base_binding_query(db):
    return db.query(RepoBinding).options(
        selectinload(RepoBinding.submission).selectinload(AssignmentSubmission.members),
        selectinload(RepoBinding.commits),
    )


def _load_binding(db, binding_id: int) -> RepoBinding | None:
    return _base_binding_query(db).filter(RepoBinding.id == int(binding_id)).first()


def enqueue_repo_preload(binding_id: int | None, force: bool = False) -> None:
    try:
        bid = int(binding_id or 0)
    except Exception:
        bid = 0
    if bid <= 0:
        return
    with _queue_lock:
        if bid in _active_binding_ids:
            return
        _pending_binding_requests[bid] = bool(force or _pending_binding_requests.get(bid, False))
    _wake_event.set()


def get_repo_preload_state(binding_id: int | None) -> str:
    try:
        bid = int(binding_id or 0)
    except Exception:
        bid = 0
    if bid <= 0:
        return "idle"
    with _queue_lock:
        if bid in _active_binding_ids:
            return "refreshing"
        if bid in _pending_binding_requests:
            return "queued"
    return "idle"


def _set_binding_active(binding_id: int, active: bool) -> None:
    with _queue_lock:
        if active:
            _active_binding_ids.add(int(binding_id))
        else:
            _active_binding_ids.discard(int(binding_id))


def _pop_pending_binding_requests(limit: int) -> list[tuple[int, bool]]:
    with _queue_lock:
        items = sorted(_pending_binding_requests.items(), key=lambda item: item[0])[: max(1, int(limit))]
        for binding_id, _ in items:
            _pending_binding_requests.pop(binding_id, None)
    return [(int(binding_id), bool(force)) for binding_id, force in items]


def _is_binding_analysis_due(binding: RepoBinding) -> bool:
    if not bool(binding.auto_sync_enabled):
        return False
    cached = load_cached_repo_insight_snapshot(binding)
    return repo_insight_needs_refresh(binding, cached)


def _due_bindings(db, now: datetime, limit: int) -> list[RepoBinding]:
    rows = (
        _base_binding_query(db)
        .order_by(RepoBinding.updated_at.desc(), RepoBinding.id.desc())
        .limit(max(1, int(limit)) * 6)
        .all()
    )
    due: list[RepoBinding] = []
    for binding in rows:
        if _is_binding_due(binding, now) or _is_binding_analysis_due(binding):
            due.append(binding)
        if len(due) >= max(1, int(limit)):
            break
    return due


def _refresh_binding(db, binding: RepoBinding, now: datetime, force: bool = False) -> tuple[bool, bool, int]:
    synced = False
    analyzed = False
    commits_inserted = 0
    _set_binding_active(binding.id, True)
    try:
        should_sync = force or _is_binding_due(binding, now) or str(binding.sync_status or "").lower() in {"never_synced", "failed"}
        if should_sync:
            commits_inserted = sync_gitee_repo(db, binding, max_pages=int(_settings.repo_auto_sync_max_pages))
            binding.last_auto_sync_at = now
            db.add(binding)
            db.commit()
            db.refresh(binding)
            synced = True

        cached = load_cached_repo_insight_snapshot(binding)
        should_analyze = force or synced or repo_insight_needs_refresh(binding, cached)
        if should_analyze:
            build_repo_insight_snapshot(db, binding, refresh=True)
            analyzed = True
        return synced, analyzed, commits_inserted
    finally:
        _set_binding_active(binding.id, False)


def run_due_repo_syncs(force: bool = False) -> dict[str, int | str]:
    if not _sync_lock.acquire(blocking=False):
        return {
            "bindings_scanned": 0,
            "bindings_synced": 0,
            "analyses_refreshed": 0,
            "commits_inserted": 0,
            "message": "调度器正在运行中",
        }

    _runtime.running = True
    _runtime.last_run_at = _current_local_time()
    scanned = 0
    synced = 0
    analyses_refreshed = 0
    commits_inserted = 0
    try:
        now = _current_local_time()
        is_startup_run = _runtime.last_success_at is None
        batch_size = max(1, int(_settings.repo_preload_batch_size or 4))
        if is_startup_run and not force:
            batch_size = max(batch_size, int(_settings.repo_startup_preload_batch_size or 200))
        db = SessionLocal()
        try:
            pending_requests = _pop_pending_binding_requests(batch_size if not force else 1000000)
            handled_ids: set[int] = set()

            for binding_id, pending_force in pending_requests:
                binding = _load_binding(db, binding_id)
                if not binding:
                    continue
                scanned += 1
                try:
                    did_sync, did_analyze, inserted = _refresh_binding(db, binding, now, force=bool(force or pending_force))
                    if did_sync:
                        synced += 1
                        commits_inserted += int(inserted or 0)
                    if did_analyze:
                        analyses_refreshed += 1
                    handled_ids.add(int(binding.id))
                except Exception as exc:
                    db.rollback()
                    binding.last_error = str(exc)
                    db.add(binding)
                    db.commit()
            if force:
                bindings = _base_binding_query(db).order_by(RepoBinding.id.asc()).all()
            else:
                bindings = _due_bindings(db, now, batch_size)
            for binding in bindings:
                if int(binding.id) in handled_ids:
                    continue
                scanned += 1
                try:
                    did_sync, did_analyze, inserted = _refresh_binding(db, binding, now, force=bool(force))
                    if did_sync:
                        synced += 1
                        commits_inserted += int(inserted or 0)
                    if did_analyze:
                        analyses_refreshed += 1
                except Exception as exc:
                    db.rollback()
                    binding.last_error = str(exc)
                    db.add(binding)
                    db.commit()
            _runtime.last_success_at = _current_local_time()
            _runtime.last_result = f"扫描 {scanned} 个仓库，同步 {synced} 个，刷新分析 {analyses_refreshed} 个，新增提交 {commits_inserted} 条"
            return {
                "bindings_scanned": scanned,
                "bindings_synced": synced,
                "analyses_refreshed": analyses_refreshed,
                "commits_inserted": commits_inserted,
                "message": _runtime.last_result or "完成",
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
                _runtime.last_result = f"调度器异常：{exc}"
        _wake_event.clear()
        if _stop_event.wait(0):
            break
        if _wake_event.wait(interval_seconds):
            continue


def start_repo_scheduler() -> None:
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _wake_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, name="repo-auto-sync", daemon=True)
    _worker_thread.start()


def stop_repo_scheduler() -> None:
    _stop_event.set()
    _wake_event.set()
