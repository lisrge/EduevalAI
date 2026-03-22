from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import get_settings


def ensure_storage_dirs() -> None:
    settings = get_settings()
    settings.application_storage_path.mkdir(parents=True, exist_ok=True)
    settings.export_storage_path.mkdir(parents=True, exist_ok=True)
    settings.preview_storage_path.mkdir(parents=True, exist_ok=True)


async def save_upload_file(upload_file: UploadFile) -> tuple[str, str]:
    ensure_storage_dirs()
    settings = get_settings()

    original_name = upload_file.filename or "application"
    safe_name = os.path.basename(original_name)
    file_id = uuid4().hex
    target_path = settings.application_storage_path / f"{file_id}_{safe_name}"

    content = await upload_file.read()
    if not content:
        raise ValueError("empty file")

    Path(target_path).write_bytes(content)
    return str(target_path), original_name

