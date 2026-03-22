from __future__ import annotations

import hashlib
import hmac
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User, UserSession

STUDENT_ID_PATTERN = re.compile(r"^\d{12}$")


def validate_student_id(student_id: str) -> str:
    sid = (student_id or "").strip()
    if not STUDENT_ID_PATTERN.match(sid):
        raise HTTPException(status_code=400, detail="student_id must be 12 digits")
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


async def create_user(db: Session, student_id: str, password: str, signature: UploadFile) -> User:
    student_id = validate_student_id(student_id)
    if not signature:
        raise HTTPException(status_code=400, detail="signature is required")

    content_type = (signature.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="signature must be an image")

    existing = db.query(User).filter(User.student_id == student_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="student_id already exists")

    settings = get_settings()
    signature_dir = settings.storage_path / "signatures"
    signature_dir.mkdir(parents=True, exist_ok=True)

    original_name = signature.filename or "signature"
    safe_name = os.path.basename(original_name)
    file_id = uuid4().hex
    suffix = Path(safe_name).suffix.lower()
    target_path = signature_dir / f"{file_id}{suffix or '.png'}"

    data = await signature.read()
    if not data:
        raise HTTPException(status_code=400, detail="signature file is empty")
    target_path.write_bytes(data)

    salt = os.urandom(16).hex()
    pwd_hash = _hash_password(password, salt)

    user = User(
        student_id=student_id,
        password_salt=salt,
        password_hash=pwd_hash,
        signature_file_name=safe_name,
        signature_path=str(target_path),
        created_at=datetime.utcnow(),
    )
    db.add(user)
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
