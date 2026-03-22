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

