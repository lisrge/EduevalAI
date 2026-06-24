from __future__ import annotations

import hashlib
import hmac
import os
import re
import base64
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User, UserSession

STUDENT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]{1,50}$")
DEFAULT_SIGNATURE_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/er8x+AAAAAASUVORK5CYII="
DEFAULT_SIGNATURE_BYTES = base64.b64decode(DEFAULT_SIGNATURE_BASE64)
DEFAULT_SIGNATURE_SHA256 = hashlib.sha256(DEFAULT_SIGNATURE_BYTES).hexdigest()


def validate_student_id(student_id: str) -> str:
    sid = (student_id or "").strip()
    if not STUDENT_ID_PATTERN.match(sid):
        raise HTTPException(status_code=400, detail="账号必须为1-50位字母、数字、下划线或连字符")
    return sid


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_password(password: str, salt_hex: str) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        (password or "").encode("utf-8"),
        bytes.fromhex(salt_hex),
        200_000,
    )
    return dk.hex()


def verify_password(password: str, salt_hex: str, expected_hash: str) -> bool:
    actual = _hash_password(password, salt_hex)
    return hmac.compare_digest(actual, expected_hash)


def _signature_storage_dir() -> Path:
    settings = get_settings()
    signature_dir = settings.storage_path / "signatures"
    signature_dir.mkdir(parents=True, exist_ok=True)
    return signature_dir


def user_has_real_signature(user: User) -> bool:
    path_value = str(getattr(user, "signature_path", "") or "").strip()
    if not path_value:
        return False
    path = Path(path_value)
    if not path.exists() or not path.is_file():
        return False
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return False
    return digest != DEFAULT_SIGNATURE_SHA256


async def save_signature_for_user(db: Session, user: User, signature: UploadFile) -> User:
    content_type = (signature.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="signature must be an image")

    original_name = signature.filename or "signature"
    safe_name = os.path.basename(original_name)
    suffix = Path(safe_name).suffix.lower()
    target_path = _signature_storage_dir() / f"{uuid4().hex}{suffix or '.png'}"

    data = await signature.read()
    if not data:
        raise HTTPException(status_code=400, detail="signature file is empty")
    target_path.write_bytes(data)

    old_path_value = str(getattr(user, "signature_path", "") or "").strip()
    user.signature_file_name = safe_name
    user.signature_path = str(target_path)
    db.commit()
    db.refresh(user)

    old_path = Path(old_path_value) if old_path_value else None
    if old_path and old_path.exists() and old_path.is_file():
        try:
            old_digest = hashlib.sha256(old_path.read_bytes()).hexdigest()
            if old_digest == DEFAULT_SIGNATURE_SHA256 and old_path != target_path:
                old_path.unlink(missing_ok=True)
        except Exception:
            pass
    return user


async def create_user(db: Session, student_id: str, real_name: str, password: str, signature: UploadFile) -> User:
    student_id = validate_student_id(student_id)
    real_name = (real_name or "").strip()
    if not real_name:
        raise HTTPException(status_code=400, detail="real_name is required")
    if not signature:
        raise HTTPException(status_code=400, detail="signature is required")

    content_type = (signature.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="signature must be an image")

    existing = db.query(User).filter(User.student_id == student_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="student_id already exists")

    original_name = signature.filename or "signature"
    safe_name = os.path.basename(original_name)
    suffix = Path(safe_name).suffix.lower()
    target_path = _signature_storage_dir() / f"{uuid4().hex}{suffix or '.png'}"

    data = await signature.read()
    if not data:
        raise HTTPException(status_code=400, detail="signature file is empty")
    target_path.write_bytes(data)

    salt = os.urandom(16).hex()
    pwd_hash = _hash_password(password, salt)

    user = User(
        student_id=student_id,
        real_name=real_name,
        password_salt=salt,
        password_hash=pwd_hash,
        role="user",
        is_root_admin=False,
        signature_file_name=safe_name,
        signature_path=str(target_path),
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    root_exists = db.query(User).filter(User.is_root_admin == True).count()
    if root_exists == 0:
        first = db.query(User).order_by(User.id.asc()).first()
        if first and first.id == user.id:
            user.role = "admin"
            user.is_root_admin = True
            db.commit()
            db.refresh(user)
    return user


def create_user_basic(db: Session, student_id: str, real_name: str, password: str) -> User:
    student_id = validate_student_id(student_id)
    real_name = (real_name or "").strip()
    if not real_name:
        raise HTTPException(status_code=400, detail="real_name is required")

    existing = db.query(User).filter(User.student_id == student_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="student_id already exists")

    salt = os.urandom(16).hex()
    pwd_hash = _hash_password(password, salt)

    user = User(
        student_id=student_id,
        real_name=real_name,
        password_salt=salt,
        password_hash=pwd_hash,
        role="user",
        is_root_admin=False,
        signature_file_name="",
        signature_path="",
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    root_exists = db.query(User).filter(User.is_root_admin == True).count()
    if root_exists == 0:
        first = db.query(User).order_by(User.id.asc()).first()
        if first and first.id == user.id:
            user.role = "admin"
            user.is_root_admin = True
            db.commit()
            db.refresh(user)
    return user


def create_session(db: Session, user: User, remember_me: bool) -> str:
    token = uuid4().hex + uuid4().hex
    token_hash = _sha256_hex(token)
    now = datetime.utcnow()
    expires_at = now + timedelta(days=30) if remember_me else now + timedelta(days=1)

    session = UserSession(
        user_id=user.id,
        token_hash=token_hash,
        created_at=now,
        last_used_at=now,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    return token


def get_user_by_token(db: Session, token: str) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="not authenticated")

    token_hash = _sha256_hex(token)
    session = db.query(UserSession).filter(UserSession.token_hash == token_hash).first()
    if not session:
        raise HTTPException(status_code=401, detail="invalid token")

    now = datetime.utcnow()
    if session.expires_at and session.expires_at < now:
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=401, detail="token expired")

    session.last_used_at = now
    db.commit()

    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="invalid token")
    return user


def delete_session(db: Session, token: str) -> None:
    if not token:
        return
    token_hash = _sha256_hex(token)
    session = db.query(UserSession).filter(UserSession.token_hash == token_hash).first()
    if not session:
        return
    db.delete(session)
    db.commit()


def change_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    if not verify_password(old_password, user.password_salt, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")

    salt = os.urandom(16).hex()
    pwd_hash = _hash_password(new_password, salt)
    user.password_salt = salt
    user.password_hash = pwd_hash
    db.commit()
