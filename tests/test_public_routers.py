from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Article, Category, CategoryTemplate, CustomUser, Expert
from app.db.session import Base, get_db
from app.main import app


@pytest.fixture()
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with test_session() as db:
        user = CustomUser(
            email="expert@example.com",
            password="unused-test-hash",
            first_name="Ari",
            last_name="Example",
            is_provider=True,
        )
        category = Category(
            name="Health",
            slug="health",
            description="Health information",
            content_type="medical",
            icon_name="heart",
            color_code="#ff0000",
            order=1,
            is_active=True,
        )
        inactive_category = Category(
            name="Inactive",
            slug="inactive",
            content_type="general",
            order=2,
            is_active=False,
        )
        db.add_all([user, category, inactive_category])
        db.flush()
        db.add_all(
            [
                CategoryTemplate(category_id=category.id, template_json={"sections": ["summary"]}),
                Expert(
                    user_id=user.id,
                    profession="doctor",
                    status="verified",
                    slug="ari-example",
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                Article(
                    author_id=user.id,
                    category_id=category.id,
                    title="A published article",
                    summary="An informative published article summary.",
                    body="Health information " * 20,
                    status="published",
                    slug="published-article",
                    reading_time=2,
                    view_count=0,
                    save_count=3,
                    published_at=datetime(2026, 10, 16, tzinfo=timezone.utc),
                ),
                Article(
                    author_id=user.id,
                    category_id=category.id,
                    title="A draft article",
                    summary="This article must stay private.",
                    body="Draft content " * 20,
                    status="draft",
                    slug="draft-article",
                    reading_time=1,
                    view_count=0,
                    save_count=0,
                ),
            ]
        )
        db.commit()

    def override_get_db() -> Iterator[Session]:
        with test_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_category_routes_return_active_categories_and_template(client: TestClient) -> None:
    categories = client.get("/api/categories/")

    assert categories.status_code == 200
    assert [item["slug"] for item in categories.json()] == ["health"]
    assert categories.json()[0]["content_type_display"] == "Medical"

    category = client.get("/api/categories/health/")
    assert category.status_code == 200
    assert category.json()["template"] == {"sections": ["summary"]}


def test_category_route_returns_documented_not_found_shape(client: TestClient) -> None:
    response = client.get("/api/categories/missing/")

    assert response.status_code == 404
    assert response.json()["message"] == "Category not found."


def test_article_list_is_paginated_and_hides_unpublished_articles(client: TestClient) -> None:
    response = client.get("/api/articles/")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert [item["slug"] for item in response.json()["results"]] == ["published-article"]
    assert response.json()["results"][0]["author_name"] == "Ari Example"


def test_article_filters_search_by_category_and_verified_profession(client: TestClient) -> None:
    response = client.get(
        "/api/articles/?category=health&profession=doctor&search=informative"
    )

    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_article_detail_increments_views_and_includes_nested_author(client: TestClient) -> None:
    response = client.get("/api/articles/published-article/")

    assert response.status_code == 200
    assert response.json()["view_count"] == 1
    assert response.json()["author"]["expert_profile"]["profession"] == "doctor"
    assert response.json()["is_author"] is False


def test_article_list_rejects_invalid_pagination_as_contract_validation_error(
    client: TestClient,
) -> None:
    response = client.get("/api/articles/?page=0")

    assert response.status_code == 400
    assert response.json()["status"] == "error"
    assert "page" in response.json()["errors"]


def test_article_detail_does_not_expose_unpublished_articles(client: TestClient) -> None:
    response = client.get("/api/articles/draft-article/")

    assert response.status_code == 404
    assert response.json()["message"] == "Article not found."
