from datetime import datetime

from pydantic import BaseModel


class ProfileResponse(BaseModel):
    student_id: str
    created_at: datetime
    signature_file_name: str
    signature_url: str


class ChangePasswordPayload(BaseModel):
    old_password: str
    new_password: str


class ChangePasswordResponse(BaseModel):
    message: str


class BlogCountInfo(BaseModel):
    normal: int = 0
    abnormal: int = 0


class AdminUserListItem(BaseModel):
    id: int
    student_id: str
    role: str
    is_root_admin: bool = False
    blog: BlogCountInfo
    application_draft_count: int = 0
    task_draft_count: int = 0


class UpdateUserRolePayload(BaseModel):
    role: str


class UpdateUserRoleResponse(BaseModel):
    id: int
    role: str


class BlogItem(BaseModel):
    id: int
    title: str
    url: str
    status: str
