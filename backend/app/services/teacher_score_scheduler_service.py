from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.base import SessionLocal
from app.models.course import Assignment
from app.models.repository import RepoBinding
from app.models.submission import AssignmentSubmission
from app.models.teacher_review_assignment import TeacherReviewAssignment
from app.models.teacher_score import TeacherScoreRecord
from app.services.teacher_score_service import (
    load_cached_teacher_score_recommendation,
    refresh_teacher_score_recommendation,
    teacher_score_recommendation_needs_refresh,
)


@dataclass
class TeacherScoreSchedulerRuntime:
    running: bool = False
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    last_result: str | None = None


_settings = get_settings()
_runtime = TeacherScoreSchedulerRuntime()
_stop_event = threading.Event()
_wake_event = threading.Event()
_worker_thread: threading.Thread | None = None
_refresh_lock = threading.Lock()
_queue_lock = threading.Lock()
_pending_submission_ids: set[int] = set()


def _utcnow() -> datetime:
    return datetime.utcnow()


def _base_submission_query(db: Session):
    return db.query(AssignmentSubmission).options(
        selectinload(AssignmentSubmission.assignment).selectinload(Assignment.course),
        selectinload(AssignmentSubmission.assets),
        selectinload(AssignmentSubmission.members),
        selectinload(AssignmentSubmission.code_analysis),
        selectinload(AssignmentSubmission.repo_binding).selectinload(RepoBinding.commits),
        selectinload(AssignmentSubmission.teacher_scores).selectinload(TeacherScoreRecord.teacher),
        selectinload(AssignmentSubmission.teacher_assignments).selectinload(TeacherReviewAssignment.teacher),
    )


def _load_submission(db: Session, submission_id: int) -> AssignmentSubmission | None:
    return (
        _base_submission_query(db)
        .filter(AssignmentSubmission.id == int(submission_id))
        .first()
    )


def enqueue_teacher_score_refresh(submission_id: int | None) -> None:
    try:
        sid = int(submission_id or 0)
    except Exception:
        sid = 0
    if sid <= 0:
        return
    with _queue_lock:
        _pending_submission_ids.add(sid)
    _wake_event.set()


def _pop_pending_submission_ids(limit: int) -> list[int]:
    with _queue_lock:
        items = sorted(_pending_submission_ids)[: max(1, int(limit))]
        for item in items:
            _pending_submission_ids.discard(item)
    return items


def _due_submissions(db: Session, limit: int) -> list[AssignmentSubmission]:
    rows = (
        _base_submission_query(db)
        .filter(AssignmentSubmission.status == "submitted")
        .order_by(AssignmentSubmission.updated_at.desc(), AssignmentSubmission.id.desc())
        .limit(max(1, int(limit)) * 4)
        .all()
    )
    due: list[AssignmentSubmission] = []
    for submission in rows:
        cached = load_cached_teacher_score_recommendation(submission)
        if teacher_score_recommendation_needs_refresh(submission, cached):
            due.append(submission)
        if len(due) >= max(1, int(limit)):
            break
    return due


def run_teacher_score_refreshes(force: bool = False) -> dict[str, int | str]:
    if not _refresh_lock.acquire(blocking=False):
        return {"submissions_scanned": 0, "submissions_refreshed": 0, "message": "teacher score scheduler already running"}

    _runtime.running = True
    _runtime.last_run_at = _utcnow()
    scanned = 0
    refreshed = 0
    try:
        batch_size = max(1, int(_settings.teacher_score_refresh_batch_size or 10))
        db = SessionLocal()
        try:
            pending_ids = _pop_pending_submission_ids(batch_size)
            handled_ids: set[int] = set()
            for submission_id in pending_ids:
                submission = _load_submission(db, submission_id)
                if submission is None or str(submission.status or "").lower() != "submitted":
                    continue
                scanned += 1
                try:
                    refresh_teacher_score_recommendation(db, submission)
                    refreshed += 1
                    handled_ids.add(int(submission.id))
                except Exception as exc:
                    db.rollback()
                    _runtime.last_result = f"refresh submission {submission_id} failed: {exc}"

            if force or refreshed < batch_size:
                for submission in _due_submissions(db, batch_size):
                    if int(submission.id) in handled_ids:
                        continue
                    scanned += 1
                    try:
                        refresh_teacher_score_recommendation(db, submission)
                        refreshed += 1
                    except Exception as exc:
                        db.rollback()
                        _runtime.last_result = f"refresh submission {submission.id} failed: {exc}"

            _runtime.last_success_at = _utcnow()
            _runtime.last_result = f"scanned={scanned}, refreshed={refreshed}"
            return {
                "submissions_scanned": scanned,
                "submissions_refreshed": refreshed,
                "message": _runtime.last_result or "ok",
            }
        finally:
            db.close()
    finally:
        _runtime.running = False
        _refresh_lock.release()


def _worker_loop() -> None:
    interval_seconds = max(300, int(_settings.teacher_score_refresh_poll_minutes or 120) * 60)
    while not _stop_event.is_set():
        try:
            if bool(_settings.teacher_score_refresh_enabled):
                run_teacher_score_refreshes(force=False)
        except Exception as exc:
            _runtime.last_run_at = _utcnow()
            _runtime.last_result = f"teacher score scheduler error: {exc}"
        _wake_event.clear()
        if _stop_event.wait(0):
            break
        if _wake_event.wait(interval_seconds):
            continue


def start_teacher_score_scheduler() -> None:
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _wake_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, name="teacher-score-refresh", daemon=True)
    _worker_thread.start()


def stop_teacher_score_scheduler() -> None:
    _stop_event.set()
    _wake_event.set()
