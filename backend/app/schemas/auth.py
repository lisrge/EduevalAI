from datetime import datetime

from pydantic import BaseModel


class UserPublic(BaseModel):
    id: int
    student_id: str
    real_name: str = ""
    role: str
    is_root_admin: bool = False
    group_id: int | None = None
    application_reupload_allowed: bool = False
    created_at: datetime


class LoginPayload(BaseModel):
    student_id: str
    password: str
    remember_me: bool = False


class RegisterPayload(BaseModel):
    student_id: str
    real_name: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: UserPublic


class MeResponse(BaseModel):
    user: UserPublic
