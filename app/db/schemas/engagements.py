from datetime import datetime
from typing import Literal

from pydantic import Field

from app.db.schemas.articles import ArticleList
from app.db.schemas.common import RequestSchema, ResponseSchema


class ArticleIdRequest(RequestSchema):
    article_id: int = Field(gt=0)


class SavedArticleRead(ResponseSchema):
    id: int
    article: ArticleList
    saved_at: datetime


class ReadHistoryRead(ResponseSchema):
    id: int
    article: ArticleList
    read_at: datetime


class SavedCountResponse(ResponseSchema):
    status: Literal["success"] = "success"
    saved_count: int = Field(ge=0)


class SavedStatusResponse(ResponseSchema):
    status: Literal["success"] = "success"
    is_saved: bool


class EngagementResponse(ResponseSchema):
    status: Literal["success", "info"] = "success"
    message: str
    saved_article: SavedArticleRead | None = None


class EngagementMessageResponse(ResponseSchema):
    status: Literal["success", "info"] = "success"
    message: str


class ArticleStatsRead(ResponseSchema):
    article_id: int
    total_saves: int = Field(ge=0)
    total_reads: int = Field(ge=0)
    unique_readers: int = Field(ge=0)
    engagement_score: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime
