from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.db.models.expert import ExpertBadgeTier, ExpertStatus
from app.db.models.payment import VerificationPaymentStatus
from app.db.schemas.articles import ArticleList
from app.db.schemas.common import RequestSchema, ResponseSchema


class ExpertApplicationRequest(RequestSchema):
    profession: str = Field(min_length=1, max_length=150)
    license_number: str = Field(min_length=1, max_length=120)
    license_issuer: str = Field(min_length=1, max_length=200)
    bio: str | None = None
    expertise_areas: str | None = None
    organization: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=160)
    languages: str | None = Field(default=None, max_length=255)
    consultation_methods: str | None = Field(default=None, max_length=255)


class ExpertProfileUpdateRequest(RequestSchema):
    bio: str | None = None
    expertise_areas: str | None = None
    organization: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=160)
    languages: str | None = Field(default=None, max_length=255)
    consultation_methods: str | None = Field(default=None, max_length=255)


class ExpertVerificationRequest(RequestSchema):
    status: Literal["verified", "rejected"]
    badge_tier: ExpertBadgeTier | None = None
    rejection_reason: str | None = None

    @model_validator(mode="after")
    def rejection_requires_reason(self) -> "ExpertVerificationRequest":
        if self.status == "rejected" and not (self.rejection_reason or "").strip():
            raise ValueError("A rejection reason is required.")
        return self


class ExpertApplicationResponse(ResponseSchema):
    status: Literal["success"] = "success"
    message: str
    expert_id: int
    application_status: Literal["awaiting_payment"] = "awaiting_payment"


class VerificationPaymentConfigResponse(ResponseSchema):
    available: bool
    provider: Literal["mpesa"] = "mpesa"
    amount: int
    currency: Literal["KES"] = "KES"


class VerificationPaymentRequest(RequestSchema):
    phone_number: str = Field(min_length=9, max_length=16)


class VerificationPaymentAttemptResponse(ResponseSchema):
    expert_id: int
    payment_id: int
    payment_status: VerificationPaymentStatus
    amount: int
    currency: Literal["KES"] = "KES"
    customer_message: str | None = None


class MyVerificationPaymentResponse(ResponseSchema):
    expert_id: int
    expert_status: ExpertStatus
    documents_uploaded: int
    payment_id: int | None = None
    payment_status: VerificationPaymentStatus | None = None
    amount: int | None = None
    currency: Literal["KES"] = "KES"
    customer_message: str | None = None


class ExpertListQuery(RequestSchema):
    profession: str | None = None
    search: str | None = None
    page: int = Field(default=1, ge=1, le=10000)


class ExpertRead(ResponseSchema):
    id: int
    user_id: int
    profession: str
    license_number: str | None
    license_issuer: str | None
    bio: str | None
    expertise_areas: str | None
    organization: str | None
    location: str | None
    languages: str | None
    consultation_methods: str | None
    status: ExpertStatus
    badge_tier: ExpertBadgeTier
    verified_by_id: int | None
    verified_at: datetime | None
    rejection_reason: str | None
    slug: str
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class ExpertListItem(ResponseSchema):
    id: int
    slug: str
    name: str
    profile_image: str | None = None
    profession: str
    profession_display: str
    bio: str | None
    organization: str | None
    location: str | None
    badge_tier: ExpertBadgeTier
    badge_display: str
    article_count: int = Field(ge=0)
    verified_at: datetime | None


class ExpertPublicProfile(ResponseSchema):
    id: int
    slug: str
    name: str
    profile_image: str | None = None
    profession: str
    profession_display: str
    bio: str | None
    expertise_areas: str | None
    organization: str | None
    location: str | None
    languages: str | None
    consultation_methods: str | None
    badge_tier: ExpertBadgeTier
    badge_display: str
    article_count: int = Field(ge=0)
    verified_at: datetime | None
    vouch_count: int = Field(ge=0)
    vouches: list[dict]
    articles: list[ArticleList]


class ExpertProfileResponse(ResponseSchema):
    status: Literal["success"] = "success"
    expert: ExpertRead


class ExpertProfileUpdateResponse(ResponseSchema):
    status: Literal["success"] = "success"
    message: str
    expert: ExpertRead


class ExpertVerificationResponse(ResponseSchema):
    status: Literal["success"] = "success"
    message: str
    expert: ExpertRead
