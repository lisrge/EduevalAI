from __future__ import annotations

import queue
import re
import threading
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.blog import BlogCrawlRun
from app.models.group import UserGroup  # needed for FK resolution
from app.models.user import User
from app.services.blog_crawler_service import create_crawl_run, run_user_blog_crawl

_queue: queue.Queue[int] = queue.Queue()
_queued_ids: set[int] = set()
_lock = threading.Lock()
_stop_event = threading.Event()
_worker: threading.Thread | None = None


def _enqueue_run_id(run_id: int) -> None:
    with _lock:
        if run_id in _queued_ids:
            return
        _queued_ids.add(run_id)
    _queue.put(run_id)


def queue_user_blog_crawls(db: Session, users: list[User], admin: User) -> tuple[list[BlogCrawlRun], list[dict]]:
    """Enqueue blog crawls for multiple users. Returns (runs, skipped).

    Each skipped entry has: user_id, student_id, reason.
    Users with active queued/running crawls are re-enqueued (not duplicated).
    """
    runs: list[BlogCrawlRun] = []
    skipped: list[dict] = []
    for user in users:
        try:
            active = (
                db.query(BlogCrawlRun)
                .filter(BlogCrawlRun.user_id == user.id, BlogCrawlRun.status.in_(["queued", "running"]))
                .order_by(BlogCrawlRun.id.desc())
                .first()
            )
            if active:
                runs.append(active)
                _enqueue_run_id(active.id)
                continue
            run = create_crawl_run(db, user, admin)
            runs.append(run)
            _enqueue_run_id(run.id)
        except ValueError as exc:
            db.rollback()
            # Create a failed run record so the admin can see why
            try:
                run = BlogCrawlRun(
                    user_id=user.id,
                    blog_home_url=(user.blog_home_url or "")[:800],
                    status="failed",
                    triggered_by_admin_id=admin.id,
                    error_message=str(exc),
                    created_at=datetime.utcnow(),
                    finished_at=datetime.utcnow(),
                )
                db.add(run)
                db.commit()
                runs.append(run)
            except Exception:
                db.rollback()
                skipped.append({"user_id": user.id, "student_id": user.student_id, "reason": str(exc)})
        except Exception as exc:
            db.rollback()
            skipped.append({"user_id": user.id, "student_id": user.student_id, "reason": str(exc)})
    return runs, skipped


def _mark_failed(db: Session, run_id: int, message: str) -> None:
    run = db.query(BlogCrawlRun).filter(BlogCrawlRun.id == run_id).first()
    if not run:
        return
    run.status = "failed"
    run.error_message = message[:4000]
    run.finished_at = datetime.utcnow()
    user = db.query(User).filter(User.id == run.user_id).first()
    if user:
        user.blog_crawl_status = "failed"
        user.blog_last_crawled_at = run.finished_at
    db.commit()


def _should_retry(error_message: str) -> bool:
    """Check if a crawl failure is recoverable (likely anti-bot or network)."""
    recoverable = (
        "Target page, context or browser has been closed",
        "Target closed",
        "net::ERR_",
        "Timeout",
        "timeout",
        "Connection",
        "Protocol error",
    )
    return any(phrase in error_message for phrase in recoverable)


def _retry_number(error_message: str) -> int:
    match = re.match(r"\[retry (\d+)/2\]", error_message or "")
    return int(match.group(1)) if match else 0


def _process_run(run_id: int) -> bool:
    """Process a run and return whether the worker should enqueue it again."""
    import time as _time, logging as _logging
    _log = _logging.getLogger("blog_crawl")

    db = SessionLocal()
    t_start = _time.monotonic()
    try:
        run = db.query(BlogCrawlRun).filter(BlogCrawlRun.id == run_id).first()
        if not run or run.status not in {"queued", "running"}:
            return False
        user = db.query(User).filter(User.id == run.user_id).first()
        admin = db.query(User).filter(User.id == run.triggered_by_admin_id).first()
        if not user or not admin:
            _mark_failed(db, run_id, "user or triggering admin no longer exists")
            return False
        _log.info("Crawl start: run=%d user=%s url=%s", run_id, user.student_id, user.blog_home_url[:80])
        user.blog_crawl_status = "running"
        db.commit()
        run_user_blog_crawl(db=db, user=user, admin=admin, existing_run=run)
        elapsed = _time.monotonic() - t_start
        _log.info("Crawl done: run=%d user=%s status=%s elapsed=%.0fs", run_id, user.student_id, run.status, elapsed)
        return False
    except Exception as exc:
        db.rollback()
        elapsed = _time.monotonic() - t_start
        error_msg = str(exc)
        _log.error("Crawl error: run=%d elapsed=%.0fs error=%s", run_id, elapsed, error_msg[:200])
        # Auto-retry: re-enqueue up to 2 times for recoverable errors
        retry_count = _retry_number(run.error_message if run else "")
        if retry_count < 2 and _should_retry(error_msg):
            run = db.query(BlogCrawlRun).filter(BlogCrawlRun.id == run_id).first()
            if run:
                run.status = "queued"
                run.error_message = f"[retry {retry_count + 1}/2] {error_msg[:3900]}"
                db.commit()
                _log.warning("Crawl retry: run=%d attempt=%d/2", run_id, retry_count + 1)
                return True
        _mark_failed(db, run_id, error_msg)
        return False
    finally:
        db.close()


# ── Cooldown between crawls to avoid triggering CSDN anti-bot ──
_last_crawl_finish: float = 0.0
_COOLDOWN_SECONDS: float = 10.0


def _worker_loop() -> None:
    global _last_crawl_finish
    while not _stop_event.is_set():
        try:
            run_id = _queue.get(timeout=1.0)
        except queue.Empty:
            continue

        # Enforce cooldown between crawls to avoid anti-bot detection
        import time as _time
        elapsed = _time.monotonic() - _last_crawl_finish
        if elapsed < _COOLDOWN_SECONDS:
            wait = _COOLDOWN_SECONDS - elapsed + (_time.time() % 7)  # small random jitter
            _stop_event.wait(wait)

        retry = False
        try:
            retry = _process_run(run_id)
        finally:
            _last_crawl_finish = _time.monotonic()
            with _lock:
                _queued_ids.discard(run_id)
            _queue.task_done()
        # Re-enqueue only after removing the id from the deduplication set.
        if retry and not _stop_event.wait(10):
            _enqueue_run_id(run_id)


def start_blog_crawl_worker() -> None:
    global _worker
    if _worker and _worker.is_alive():
        return
    _stop_event.clear()
    while True:
        try:
            _queue.get_nowait()
            _queue.task_done()
        except queue.Empty:
            break
    with _lock:
        _queued_ids.clear()
    db = SessionLocal()
    try:
        stale_runs = db.query(BlogCrawlRun).filter(BlogCrawlRun.status.in_(["queued", "running"])).all()
        for run in stale_runs:
            run.status = "queued"
        db.commit()
        run_ids = [run.id for run in stale_runs]
    finally:
        db.close()
    _worker = threading.Thread(target=_worker_loop, name="blog-crawl-worker", daemon=True)
    _worker.start()
    for run_id in run_ids:
        _enqueue_run_id(run_id)


def stop_blog_crawl_worker() -> None:
    _stop_event.set()
