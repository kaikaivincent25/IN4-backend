from datetime import datetime

from pydantic import Field

from app.db.schemas.common import RequestSchema, ResponseSchema


class CommentCreate(RequestSchema):
    content: str = Field(min_length=1, max_length=4000)


class CommentRead(ResponseSchema):
    id: int
    article_id: int
    user_id: int
    author_name: str
    content: str
    created_at: datetime


class ExpertProfileCommentCreate(RequestSchema):
    content: str = Field(min_length=1, max_length=1500)


class ExpertProfileCommentRead(ResponseSchema):
    id: int
    expert_id: int
    user_id: int
    author_name: str
    content: str
    created_at: datetime


class ExpertCommentEligibility(ResponseSchema):
    can_comment: bool
    read_article_count: int = Field(ge=0)
    already_commented: bool
    is_profile_owner: bool = False


class ConversationCreate(RequestSchema):
    article_id: int = Field(gt=0)


class MessageCreate(RequestSchema):
    content: str = Field(min_length=1, max_length=4000)


class MessageRead(ResponseSchema):
    id: int
    conversation_id: int
    sender_id: int
    sender_name: str
    content: str
    created_at: datetime


class ConversationRead(ResponseSchema):
    id: int
    article_id: int
    article_title: str
    article_slug: str
    other_user_id: int
    other_user_name: str
    other_user_profile_image: str | None = None
    other_user_is_expert: bool = False
    other_user_verified: bool = False
    other_user_badge_tier: str | None = None
    last_message: str | None
    last_message_at: datetime | None
    updated_at: datetime
    article_category_name: str | None = None


class ConversationMessages(ResponseSchema):
    conversation: ConversationRead
    messages: list[MessageRead]
