from datetime import datetime

from app.db.schemas.common import ResponseSchema


class UserPublic(ResponseSchema):
    id: int
    email: str
    first_name: str | None
    last_name: str | None
    profile_image: str | None = None
    is_provider: bool
    is_staff: bool
    created_at: datetime


class UserRead(UserPublic):
    is_consumer: bool
    updated_at: datetime
