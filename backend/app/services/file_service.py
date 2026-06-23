from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import get_settings


def ensure_storage_dirs() -> None:
    settings = get_settings()
    settings.application_storage_path.mkdir(parents=True, exist_ok=True)
    settings.export_storage_path.mkdir(parents=True, exist_ok=True)
    settings.preview_storage_path.mkdir(parents=True, exist_ok=True)
    settings.submission_storage_path.mkdir(parents=True, exist_ok=True)
    settings.upload_session_storage_path.mkdir(parents=True, exist_ok=True)


def _safe_name(name: str | None, fallback: str) -> str:
    raw = os.path.basename(name or fallback).strip()
    raw = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", raw).strip(". ")
    return raw[:240] or fallback


def _session_dir(upload_id: str) -> Path:
    settings = get_settings()
    return settings.upload_session_storage_path / upload_id


def _manifest_path(upload_id: str) -> Path:
    return _session_dir(upload_id) / "manifest.json"


def _part_path(upload_id: str, part_number: int) -> Path:
    return _session_dir(upload_id) / f"part_{int(part_number):06d}.bin"


def _write_manifest(upload_id: str, payload: dict) -> None:
    target = _manifest_path(upload_id)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _touch_manifest(upload_id: str, payload: dict) -> None:
    payload["updated_at"] = datetime.utcnow().isoformat()
    _write_manifest(upload_id, payload)


def _read_manifest(upload_id: str) -> dict:
    target = _manifest_path(upload_id)
    if not target.exists():
        raise FileNotFoundError("upload session not found")
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _uploaded_parts(upload_id: str) -> list[int]:
    folder = _session_dir(upload_id)
    parts: list[int] = []
    if not folder.exists():
        return parts
    for item in folder.glob("part_*.bin"):
        try:
            parts.append(int(item.stem.split("_")[-1]))
        except ValueError:
            continue
    return sorted(parts)


async def _stream_to_path(upload_file: UploadFile, target_path: Path) -> tuple[int, str]:
    file_size = 0
    digest = hashlib.sha256()
    with open(target_path, "wb") as f:
        while True:
            chunk = await upload_file.read(1024 * 1024)
            if not chunk:
                break
            file_size += len(chunk)
            digest.update(chunk)
            f.write(chunk)
    if file_size <= 0:
        raise ValueError("empty file")
    await upload_file.seek(0)
    return file_size, digest.hexdigest()


async def save_upload_file(upload_file: UploadFile) -> tuple[str, str]:
    ensure_storage_dirs()
    settings = get_settings()

    original_name = upload_file.filename or "application"
    safe_name = _safe_name(original_name, "application")
    file_id = uuid4().hex
    target_path = settings.application_storage_path / f"{file_id}_{safe_name}"

    await _stream_to_path(upload_file, Path(target_path))
    return str(target_path), original_name


async def save_user_file(upload_file: UploadFile, subdir: str) -> tuple[str, str]:
    ensure_storage_dirs()
    settings = get_settings()

    original_name = upload_file.filename or "file"
    safe_name = _safe_name(original_name, "file")
    file_id = uuid4().hex
    target_dir = settings.storage_path / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{file_id}_{safe_name}"

    await _stream_to_path(upload_file, Path(target_path))
    return str(target_path), original_name


async def save_submission_asset(
    upload_file: UploadFile,
    submission_id: int,
    asset_type: str,
    version_no: int,
) -> dict[str, str | int | None]:
    ensure_storage_dirs()
    settings = get_settings()

    original_name = upload_file.filename or f"{asset_type}"
    safe_name = _safe_name(original_name, asset_type)
    suffix = Path(safe_name).suffix
    file_id = uuid4().hex
    submission_dir = settings.submission_storage_path / str(submission_id) / asset_type
    submission_dir.mkdir(parents=True, exist_ok=True)
    target_path = submission_dir / f"v{version_no}_{file_id}{suffix}"

    file_size, file_hash = await _stream_to_path(upload_file, target_path)
    return {
        "file_name": safe_name,
        "file_path": str(target_path),
        "file_size": file_size,
        "file_hash": file_hash,
        "mime_type": upload_file.content_type,
    }


def create_chunk_upload_session(
    submission_id: int,
    asset_type: str,
    uploader_user_id: int,
    file_name: str,
    mime_type: str | None,
    total_size: int,
    total_chunks: int,
    chunk_size: int,
) -> dict:
    ensure_storage_dirs()
    upload_id = uuid4().hex
    folder = _session_dir(upload_id)
    folder.mkdir(parents=True, exist_ok=True)
    payload = {
        "upload_id": upload_id,
        "submission_id": int(submission_id),
        "asset_type": asset_type,
        "uploader_user_id": int(uploader_user_id),
        "file_name": _safe_name(file_name, asset_type),
        "mime_type": mime_type,
        "total_size": int(total_size),
        "total_chunks": int(total_chunks),
        "chunk_size": int(chunk_size),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    _write_manifest(upload_id, payload)
    payload["uploaded_parts"] = []
    payload["uploaded_count"] = 0
    return payload


def get_chunk_upload_session(upload_id: str) -> dict:
    payload = _read_manifest(upload_id)
    uploaded = _uploaded_parts(upload_id)
    payload["uploaded_parts"] = uploaded
    payload["uploaded_count"] = len(uploaded)
    total_chunks = int(payload.get("total_chunks") or 0)
    payload["is_complete"] = total_chunks > 0 and len(uploaded) == total_chunks
    return payload


def list_chunk_upload_sessions(
    uploader_user_id: int | None = None,
    submission_id: int | None = None,
) -> list[dict]:
    ensure_storage_dirs()
    settings = get_settings()
    sessions: list[dict] = []
    for folder in settings.upload_session_storage_path.iterdir():
        if not folder.is_dir():
            continue
        try:
            payload = get_chunk_upload_session(folder.name)
        except FileNotFoundError:
            continue
        if uploader_user_id is not None and int(payload.get("uploader_user_id") or 0) != int(uploader_user_id):
            continue
        if submission_id is not None and int(payload.get("submission_id") or 0) != int(submission_id):
            continue
        sessions.append(payload)
    sessions.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    return sessions


def cleanup_expired_chunk_upload_sessions() -> list[str]:
    ensure_storage_dirs()
    settings = get_settings()
    ttl = max(int(settings.upload_session_ttl_hours or 24), 1)
    threshold = datetime.utcnow() - timedelta(hours=ttl)
    removed: list[str] = []
    for folder in settings.upload_session_storage_path.iterdir():
        if not folder.is_dir():
            continue
        try:
            payload = _read_manifest(folder.name)
        except FileNotFoundError:
            continue
        updated_at = _parse_iso_datetime(payload.get("updated_at")) or _parse_iso_datetime(payload.get("created_at"))
        if updated_at and updated_at < threshold:
            clear_chunk_upload_session(folder.name)
            removed.append(folder.name)
    return removed


def save_chunk_upload_part(upload_id: str, part_number: int, data: bytes) -> dict:
    if int(part_number) < 1:
        raise ValueError("part_number must be >= 1")
    payload = _read_manifest(upload_id)
    total_chunks = int(payload.get("total_chunks") or 0)
    if total_chunks <= 0 or int(part_number) > total_chunks:
        raise ValueError("part_number out of range")
    if not data:
        raise ValueError("empty chunk")
    target = _part_path(upload_id, part_number)
    target.write_bytes(data)
    _touch_manifest(upload_id, payload)
    uploaded = _uploaded_parts(upload_id)
    return {
        "upload_id": upload_id,
        "uploaded_parts": uploaded,
        "uploaded_count": len(uploaded),
        "received_size": len(data),
        "is_complete": len(uploaded) == total_chunks,
    }


def finalize_chunk_upload(upload_id: str, version_no: int) -> dict:
    ensure_storage_dirs()
    payload = _read_manifest(upload_id)
    uploaded = _uploaded_parts(upload_id)
    total_chunks = int(payload.get("total_chunks") or 0)
    missing = [idx for idx in range(1, total_chunks + 1) if idx not in uploaded]
    if missing:
        raise ValueError(f"missing parts: {missing[:5]}")

    submission_id = int(payload["submission_id"])
    asset_type = str(payload["asset_type"])
    safe_name = _safe_name(str(payload.get("file_name") or asset_type), asset_type)
    suffix = Path(safe_name).suffix
    file_id = uuid4().hex
    settings = get_settings()
    submission_dir = settings.submission_storage_path / str(submission_id) / asset_type
    submission_dir.mkdir(parents=True, exist_ok=True)
    target_path = submission_dir / f"v{version_no}_{file_id}{suffix}"

    file_size = 0
    digest = hashlib.sha256()
    with open(target_path, "wb") as target:
        for idx in range(1, total_chunks + 1):
            chunk = _part_path(upload_id, idx).read_bytes()
            file_size += len(chunk)
            digest.update(chunk)
            target.write(chunk)

    expected_size = int(payload.get("total_size") or 0)
    if expected_size > 0 and file_size != expected_size:
        try:
            target_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise ValueError("merged file size mismatch")

    clear_chunk_upload_session(upload_id)
    return {
        "file_name": safe_name,
        "file_path": str(target_path),
        "file_size": file_size,
        "file_hash": digest.hexdigest(),
        "mime_type": payload.get("mime_type"),
    }


def clear_chunk_upload_session(upload_id: str) -> None:
    folder = _session_dir(upload_id)
    if not folder.exists():
        return
    for item in folder.iterdir():
        try:
            item.unlink(missing_ok=True)
        except OSError:
            continue
    try:
        folder.rmdir()
    except OSError:
        return


def remove_stored_file(path: str | os.PathLike[str]) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        return
