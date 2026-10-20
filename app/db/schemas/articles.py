from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, Field, model_validator

from app.db.models.article import ArticleStatus
from app.db.schemas.common import RequestSchema, ResponseSchema


class ArticleCategory(ResponseSchema):
    id: int
    slug: str
    name: str
    content_type: str
    icon_name: str | None
    color_code: str | None


class ArticleAuthorExpert(ResponseSchema):
    profession: str


class ArticleAuthor(ResponseSchema):
    id: int
    email: str
    first_name: str | None
    last_name: str | None
    profile_image: str | None = None
    expert_profile: ArticleAuthorExpert | None = None


class ArticleList(ResponseSchema):
    id: int
    slug: str
    title: str
    summary: str
    author_name: str
    author_verified: bool = False
    author_badge_tier: str | None = None
    featured_image: str | None
    category_name: str
    category_slug: str
    category_icon: str | None
    category_color: str | None
    reading_time: int = Field(ge=1)
    view_count: int = Field(ge=0)
    save_count: int = Field(ge=0)
    published_at: datetime | None
    created_at: datetime


class ArticleDetail(ArticleList):
    body: str
    status: ArticleStatus
    updated_at: datetime
    is_author: bool
    category: ArticleCategory
    author: ArticleAuthor


class ArticleWrite(RequestSchema):
    title: str = Field(min_length=10, max_length=200)
    summary: str = Field(min_length=20, max_length=500)
    body: str = Field(min_length=100)
    category_id: int = Field(gt=0)
    featured_image: str | None = Field(default=None, max_length=500)


class DraftCreate(RequestSchema):
    title: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=500)
    body: str | None = None
    category_id: int | None = Field(
        default=None,
        gt=0,
        validation_alias=AliasChoices("category_id", "category"),
    )
    featured_image: str | None = Field(default=None, max_length=500)

    @model_validator(mode="before")
    @classmethod
    def accept_duplicate_category_aliases(cls, value: Any) -> Any:
        if isinstance(value, dict) and "category_id" in value and "category" in value:
            if value["category_id"] != value["category"]:
                raise ValueError("category and category_id must match.")
            value = {key: item for key, item in value.items() if key != "category"}
        return value


class DraftSave(RequestSchema):
    title: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=500)
    body: str | None = None
    category_id: int | None = Field(
        default=None,
        gt=0,
        validation_alias=AliasChoices("category_id", "category"),
    )
    featured_image: str | None = Field(default=None, max_length=500)

    @model_validator(mode="before")
    @classmethod
    def accept_duplicate_category_aliases(cls, value: Any) -> Any:
        if isinstance(value, dict) and "category_id" in value and "category" in value:
            if value["category_id"] != value["category"]:
                raise ValueError("category and category_id must match.")
            value = {key: item for key, item in value.items() if key != "category"}
        return value


class DraftListItem(ResponseSchema):
    id: int
    title: str | None
    progress: int = Field(ge=0, le=100)
    article_id: int | None
    updated_at: datetime
    last_auto_save: datetime | None


class DraftDetail(DraftListItem):
    summary: str | None
    body: str | None
    category_id: int | None
    featured_image: str | None
    version: int = Field(ge=1)


class DraftResponse(ResponseSchema):
    status: Literal["success"] = "success"
    draft: DraftDetail


class ArticlePublishResponse(ResponseSchema):
    status: Literal["success"] = "success"
    message: str
    article: ArticleDetail


class ArticleRevisionCreate(RequestSchema):
    title: str = Field(min_length=10, max_length=200)
    summary: str = Field(min_length=20, max_length=500)
    body: str = Field(min_length=100)
    category_id: int = Field(gt=0)
    featured_image: str | None = Field(default=None, max_length=500)
    change_note: str = Field(min_length=10, max_length=2000)


class ArticleRevisionReview(RequestSchema):
    status: Literal["approved", "rejected"]
    reviewer_note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def rejection_requires_feedback(self) -> "ArticleRevisionReview":
        if self.status == "rejected" and not (self.reviewer_note or "").strip():
            raise ValueError("A reviewer note is required when rejecting an edit.")
        return self


class ArticleRevisionRead(ResponseSchema):
    id: int
    article_id: int
    article_title: str
    article_slug: str
    current_title: str
    current_summary: str
    current_body: str
    author_id: int
    author_name: str
    reviewer_id: int | None
    status: Literal["pending", "approved", "rejected"]
    title: str
    summary: str
    body: str
    category_id: int
    featured_image: str | None
    change_note: str
    reviewer_note: str | None
    previous_title: str | None
    previous_summary: str | None
    previous_body: str | None
    previous_category_id: int | None
    previous_featured_image: str | None
    created_at: datetime
    reviewed_at: datetime | None


class ArticleRevisionResponse(ResponseSchema):
    status: Literal["success"] = "success"
    message: str
    revision: ArticleRevisionRead


class ArticleListQuery(RequestSchema):
    category: str | None = None
    profession: str | None = None
    search: str | None = None
    order_by: Literal[
        "-published_at",
        "-view_count",
        "-save_count",
        "reading_time",
        "-reading_time",
    ] = "-published_at"
    page: int = Field(default=1, ge=1, le=10000)


class DraftProgress(ResponseSchema):
    progress: int = Field(ge=0, le=100)
