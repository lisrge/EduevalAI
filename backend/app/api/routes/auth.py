from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.schemas.auth import LoginPayload, LoginResponse, MeResponse, UserPublic
from app.services.auth_service import create_session, create_user, delete_session, get_user_by_token, validate_student_id, verify_password
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_public(user: User) -> UserPublic:
    return UserPublic(id=user.id, student_id=user.student_id, created_at=user.created_at)


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
    password: str = Form(...),
    signature: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = await create_user(db=db, student_id=student_id, password=password, signature=signature)
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
