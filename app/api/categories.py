from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models.category import Category, ContentType
from app.db.schemas.categories import CategoryRead, CategoryWithTemplate
from app.db.session import get_db


router = APIRouter(prefix="/api/categories", tags=["categories"])

_CONTENT_TYPE_LABELS = {
    ContentType.MEDICAL.value: "Medical",
    ContentType.LEGAL.value: "Legal",
    ContentType.FINANCIAL.value: "Financial",
    ContentType.TECHNOLOGY.value: "Technology",
    ContentType.MENTAL.value: "Mental Health",
    ContentType.AGRICULTURE.value: "Agriculture",
    ContentType.GENERAL.value: "General",
}


def _category_response(category: Category) -> CategoryRead:
    return CategoryRead(
        id=category.id,
        slug=category.slug,
        name=category.name,
        description=category.description,
        content_type=category.content_type,
        content_type_display=_CONTENT_TYPE_LABELS.get(category.content_type, category.content_type),
        icon_name=category.icon_name,
        color_code=category.color_code,
        order=category.order,
    )


@router.get("/", response_model=list[CategoryRead])
def list_categories(db: Session = Depends(get_db)) -> list[CategoryRead]:
    categories = db.scalars(
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.order, Category.name)
    ).all()
    return [_category_response(category) for category in categories]


@router.get("/{slug}/", response_model=CategoryWithTemplate)
def get_category(slug: str, db: Session = Depends(get_db)) -> CategoryWithTemplate:
    category = db.scalar(
        select(Category)
        .options(joinedload(Category.template))
        .where(Category.slug == slug, Category.is_active.is_(True))
    )
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found.")

    return CategoryWithTemplate(
        **_category_response(category).model_dump(),
        template=category.template.template_json if category.template else None,
    )
