from typing import Any

from app.db.models.category import ContentType
from app.db.schemas.common import ResponseSchema


class CategoryRead(ResponseSchema):
    id: int
    slug: str
    name: str
    description: str | None
    content_type: ContentType
    content_type_display: str
    icon_name: str | None
    color_code: str | None
    order: int


class CategoryWithTemplate(CategoryRead):
    template: Any | None = None
