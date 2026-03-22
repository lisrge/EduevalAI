from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.schemas.user_profile import ChangePasswordPayload, ChangePasswordResponse, ProfileResponse
from app.services.auth_service import change_password, get_user_by_token

router = APIRouter(prefix="/users", tags=["users"])


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    value = authorization.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return ""


def _current_user(authorization: str | None, db: Session):
    token = _bearer_token(authorization)
    return get_user_by_token(db, token)


@router.get("/me/profile", response_model=ProfileResponse)
def me_profile(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    user = _current_user(authorization, db)
    return ProfileResponse(
        student_id=user.student_id,
        created_at=user.created_at,
        signature_file_name=user.signature_file_name,
        signature_url="/api/users/me/signature",
    )


@router.get("/me/signature")
def me_signature(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    user = _current_user(authorization, db)
    path = Path(user.signature_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="signature not found")
    return FileResponse(path=path, filename=user.signature_file_name, headers={"Content-Disposition": "inline"})


@router.post("/me/password", response_model=ChangePasswordResponse)
def me_change_password(
    payload: ChangePasswordPayload,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _current_user(authorization, db)
    change_password(db, user, payload.old_password, payload.new_password)
    return ChangePasswordResponse(message="password updated")

