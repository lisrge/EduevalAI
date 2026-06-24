from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.schemas.auth import LoginPayload, LoginResponse, MeResponse, RegisterPayload, UserPublic
from app.services.auth_service import (
    create_session,
    create_user,
    create_user_basic,
    delete_session,
    get_user_by_token,
    validate_student_id,
    verify_password,
)
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        student_id=user.student_id,
        real_name=user.real_name or "",
        role=user.role,
        is_root_admin=user.is_root_admin,
        group_id=user.group_id,
        application_reupload_allowed=bool(user.application_reupload_allowed),
        created_at=user.created_at,
    )


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    value = authorization.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return ""


@router.post("/register", response_model=MeResponse)
async def register(
    student_id: str = Form(...),
    real_name: str = Form(...),
    password: str = Form(...),
    signature: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = await create_user(db=db, student_id=student_id, real_name=real_name, password=password, signature=signature)
    return MeResponse(user=_to_public(user))


@router.post("/register-basic", response_model=MeResponse)
def register_basic(payload: RegisterPayload, db: Session = Depends(get_db)):
    user = create_user_basic(db=db, student_id=payload.student_id, real_name=payload.real_name, password=payload.password)
    return MeResponse(user=_to_public(user))


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginPayload, db: Session = Depends(get_db)):
    sid = validate_student_id(payload.student_id)
    user = db.query(User).filter(User.student_id == sid).first()
    if not user or not verify_password(payload.password, user.password_salt, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")

    token = create_session(db=db, user=user, remember_me=payload.remember_me)
    return LoginResponse(token=token, user=_to_public(user))


@router.get("/me", response_model=MeResponse)
def me(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    token = _bearer_token(authorization)
    user = get_user_by_token(db, token)
    return MeResponse(user=_to_public(user))


@router.post("/logout")
def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    token = _bearer_token(authorization)
    delete_session(db, token)
    return {"message": "logged out"}
