from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.db.schemas import (
    ArticleList,
    DraftCreate,
    DraftSave,
    ExpertVerificationRequest,
    RegisterRequest,
    UserPublic,
)


def test_registration_normalizes_email_and_validates_password() -> None:
    request = RegisterRequest(
        email="USER@example.com",
        password="correct-horse-1",
        password_confirm="correct-horse-1",
        first_name="Ari",
        last_name="Example",
    )

    assert request.email == "user@example.com"


@pytest.mark.parametrize("password", ["12345678", "abcdefgh"])
def test_registration_rejects_all_numeric_or_alphabetic_passwords(password: str) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="person@example.com",
            password=password,
            password_confirm=password,
            first_name="Ari",
            last_name="Example",
        )


def test_registration_rejects_mismatched_passwords() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="person@example.com",
            password="correct-horse-1",
            password_confirm="different-horse-2",
            first_name="Ari",
            last_name="Example",
        )


def test_draft_accepts_legacy_category_alias_and_emits_canonical_field() -> None:
    draft = DraftCreate.model_validate({"title": "Draft", "category": 7})
    saved = DraftSave.model_validate({"category_id": 8})

    assert draft.category_id == 7
    assert "category_id" in draft.model_dump()
    assert "category" not in draft.model_dump()
    assert saved.category_id == 8


def test_requests_reject_unrecognized_fields_such_as_owner_id() -> None:
    with pytest.raises(ValidationError):
        DraftCreate.model_validate({"author_id": 4})


def test_expert_rejection_requires_reason() -> None:
    with pytest.raises(ValidationError):
        ExpertVerificationRequest(status="rejected")

    assert ExpertVerificationRequest(
        status="rejected",
        rejection_reason="Credentials could not be verified",
    ).status == "rejected"


def test_public_user_response_never_serializes_password_hash() -> None:
    user = UserPublic(
        id=12,
        email="person@example.com",
        first_name="Ari",
        last_name="Example",
        is_provider=False,
        created_at=datetime(2026, 10, 16, tzinfo=timezone.utc),
        password="must-not-serialize",
    )

    assert "password" not in user.model_dump()


def test_article_list_validates_contract_shape() -> None:
    article = ArticleList(
        id=41,
        slug="example-article",
        title="Example article title",
        summary="A short summary for this example article.",
        author_name="Ari Example",
        featured_image=None,
        category_name="Health",
        category_slug="health",
        category_icon="heart",
        category_color="#ff0000",
        reading_time=3,
        view_count=10,
        save_count=2,
        published_at=datetime(2026, 10, 16, 11, tzinfo=timezone.utc),
        created_at=datetime(2026, 10, 15, 11, tzinfo=timezone.utc),
    )

    assert article.reading_time == 3
