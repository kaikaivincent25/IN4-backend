import re
import unicodedata
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import (
    get_current_user,
    get_optional_user,
    get_staff_user,
    get_verified_provider,
)
from app.db.models.article import Article, ArticleDraft, ArticleRevision, ArticleRevisionStatus, ArticleStatus
from app.db.models.category import Category
from app.db.models.expert import Expert, ExpertStatus
from app.db.models.user import CustomUser
from app.db.schemas.auth import MessageResponse
from app.db.schemas.articles import (
    ArticleAuthor,
    ArticleAuthorExpert,
    ArticleCategory,
    ArticleDetail,
    ArticleList,
    ArticlePublishResponse,
    ArticleRevisionCreate,
    ArticleRevisionRead,
    ArticleRevisionResponse,
    ArticleRevisionReview,
    ArticleWrite,
    DraftCreate,
    DraftDetail,
    DraftListItem,
    DraftResponse,
    DraftSave,
)
from app.db.schemas.common import PaginatedResponse
from app.db.session import get_db


router = APIRouter(prefix="/api/articles", tags=["articles"])
PAGE_SIZE = 20
_ORDERING = {
    "-published_at": (Article.published_at.desc(), Article.id.desc()),
    "-view_count": (Article.view_count.desc(), Article.id.desc()),
    "-save_count": (Article.save_count.desc(), Article.id.desc()),
    "reading_time": (Article.reading_time.asc(), Article.id.asc()),
    "-reading_time": (Article.reading_time.desc(), Article.id.desc()),
}


def _slug_base(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "article"


def _unique_article_slug(db: Session, value: str, exclude_id: int | None = None) -> str:
    base = _slug_base(value)
    slug = base
    suffix = 2
    while True:
        query = select(Article.id).where(Article.slug == slug)
        if exclude_id is not None:
            query = query.where(Article.id != exclude_id)
        if db.scalar(query) is None:
            return slug
        slug = f"{base}-{suffix}"
        suffix += 1


def _author_name(author: CustomUser) -> str:
    name = " ".join(part for part in (author.first_name, author.last_name) if part)
    return name or author.email


def _article_list(article: Article) -> ArticleList:
    expert = article.author.expert_profile
    return ArticleList(
        id=article.id,
        slug=article.slug,
        title=article.title,
        summary=article.summary,
        author_name=_author_name(article.author),
        author_verified=bool(expert and expert.status == ExpertStatus.VERIFIED.value),
        author_badge_tier=expert.badge_tier if expert and expert.status == ExpertStatus.VERIFIED.value else None,
        featured_image=article.featured_image,
        category_name=article.category.name,
        category_slug=article.category.slug,
        category_icon=article.category.icon_name,
        category_color=article.category.color_code,
        reading_time=article.reading_time,
        view_count=article.view_count,
        save_count=article.save_count,
        published_at=article.published_at,
        created_at=article.created_at,
    )


def _article_query():
    return (
        select(Article)
        .options(
            joinedload(Article.author).joinedload(CustomUser.expert_profile),
            joinedload(Article.category),
        )
        .where(Article.status == ArticleStatus.PUBLISHED.value)
    )


def _article_detail(article: Article, is_author: bool) -> ArticleDetail:
    result = _article_list(article).model_dump()
    result.update(
        body=article.body,
        status=article.status,
        updated_at=article.updated_at,
        is_author=is_author,
        category=ArticleCategory(
            id=article.category.id,
            slug=article.category.slug,
            name=article.category.name,
            content_type=article.category.content_type,
            icon_name=article.category.icon_name,
            color_code=article.category.color_code,
        ),
        author=ArticleAuthor(
            id=article.author.id,
            email=article.author.email,
            first_name=article.author.first_name,
            last_name=article.author.last_name,
            profile_image=article.author.profile_image,
            expert_profile=(
                ArticleAuthorExpert(profession=article.author.expert_profile.profession)
                if article.author.expert_profile is not None
                else None
            ),
        ),
    )
    return ArticleDetail.model_validate(result)


def _draft_progress(draft: ArticleDraft) -> int:
    score = 0
    for value, weight in (
        (draft.title, 20),
        (draft.summary, 20),
        (draft.body, 40),
        (draft.category_id, 20),
    ):
        if value:
            score += weight
    return score


def _draft_detail(draft: ArticleDraft) -> DraftDetail:
    return DraftDetail(
        id=draft.id,
        title=draft.title,
        summary=draft.summary,
        body=draft.body,
        category_id=draft.category_id,
        featured_image=draft.featured_image,
        progress=_draft_progress(draft),
        article_id=draft.article_id,
        version=draft.version,
        updated_at=draft.updated_at,
        last_auto_save=draft.last_auto_save,
    )


def _revision_read(revision: ArticleRevision) -> ArticleRevisionRead:
    return ArticleRevisionRead(
        id=revision.id,
        article_id=revision.article_id,
        article_title=revision.article.title,
        article_slug=revision.article.slug,
        current_title=revision.article.title,
        current_summary=revision.article.summary,
        current_body=revision.article.body,
        author_id=revision.author_id,
        author_name=_author_name(revision.author),
        reviewer_id=revision.reviewer_id,
        status=revision.status,
        title=revision.title,
        summary=revision.summary,
        body=revision.body,
        category_id=revision.category_id,
        featured_image=revision.featured_image,
        change_note=revision.change_note,
        reviewer_note=revision.reviewer_note,
        previous_title=revision.previous_title,
        previous_summary=revision.previous_summary,
        previous_body=revision.previous_body,
        previous_category_id=revision.previous_category_id,
        previous_featured_image=revision.previous_featured_image,
        created_at=revision.created_at,
        reviewed_at=revision.reviewed_at,
    )


def _publication_errors(payload: ArticleDraft) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    if not payload.title or len(payload.title.strip()) < 10:
        errors["title"] = ["Title must be at least 10 characters."]
    if not payload.summary or len(payload.summary.strip()) < 20:
        errors["summary"] = ["Summary must be at least 20 characters."]
    if not payload.body or len(payload.body.strip()) < 100:
        errors["body"] = ["Article content must be at least 100 characters."]
    if payload.category_id is None:
        errors["category_id"] = ["A category is required."]
    return errors


def _raise_validation_error(errors: dict[str, list[str]]) -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "message": "Validation failed.",
            "errors": errors,
        },
    )


@router.get("/", response_model=PaginatedResponse[ArticleList])
def list_articles(
    request: Request,
    category: str | None = None,
    profession: str | None = None,
    search: str | None = None,
    order_by: str = Query(default="-published_at", pattern="^(-published_at|-view_count|-save_count|reading_time|-reading_time)$"),
    page: int = Query(default=1, ge=1, le=10000),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ArticleList]:
    filters = [Article.status == ArticleStatus.PUBLISHED.value]
    if category:
        filters.append(Category.slug == category)
    if search:
        search_term = f"%{search.strip()}%"
        filters.append(
            or_(
                Article.title.ilike(search_term),
                Article.summary.ilike(search_term),
                Article.body.ilike(search_term),
            )
        )

    count_query = select(func.count(Article.id)).join(Category).where(*filters)
    if profession:
        count_query = (
            count_query.join(Expert, Expert.user_id == Article.author_id)
            .where(
                Expert.status == ExpertStatus.VERIFIED.value,
                Expert.profession == profession,
            )
        )
    count = db.scalar(count_query) or 0

    query = _article_query().join(Category).where(*filters)
    if profession:
        query = (
            query.join(Expert, Expert.user_id == Article.author_id)
            .where(
                Expert.status == ExpertStatus.VERIFIED.value,
                Expert.profession == profession,
            )
        )

    articles = db.scalars(
        query.order_by(*_ORDERING[order_by])
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).unique().all()

    next_url = (
        str(request.url.include_query_params(page=page + 1))
        if page * PAGE_SIZE < count
        else None
    )
    previous_url = (
        str(request.url.include_query_params(page=page - 1))
        if page > 1 and count > 0
        else None
    )
    return PaginatedResponse[ArticleList](
        count=count,
        next=next_url,
        previous=previous_url,
        results=[_article_list(article) for article in articles],
    )


@router.post(
    "/drafts/",
    response_model=DraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_draft(
    payload: DraftCreate,
    user: CustomUser = Depends(get_verified_provider),
    db: Session = Depends(get_db),
) -> DraftResponse:
    draft = ArticleDraft(author_id=user.id, **payload.model_dump())
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return DraftResponse(draft=_draft_detail(draft))


@router.post("/drafts/{draft_id}/save/", response_model=DraftResponse)
def save_draft(
    draft_id: int,
    payload: DraftSave,
    user: CustomUser = Depends(get_verified_provider),
    db: Session = Depends(get_db),
) -> DraftResponse:
    draft = db.scalar(
        select(ArticleDraft)
        .where(ArticleDraft.id == draft_id, ArticleDraft.author_id == user.id)
        .with_for_update()
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found.")
    for field in payload.model_fields_set:
        setattr(draft, field, getattr(payload, field))
    draft.version += 1
    draft.is_auto_saved = True
    draft.last_auto_save = datetime.now(timezone.utc)
    db.commit()
    db.refresh(draft)
    return DraftResponse(draft=_draft_detail(draft))


@router.get("/drafts/", response_model=PaginatedResponse[DraftListItem])
def list_drafts(
    request: Request,
    page: int = Query(default=1, ge=1, le=10000),
    user: CustomUser = Depends(get_verified_provider),
    db: Session = Depends(get_db),
) -> PaginatedResponse[DraftListItem]:
    count = db.scalar(
        select(func.count(ArticleDraft.id)).where(ArticleDraft.author_id == user.id)
    ) or 0
    drafts = db.scalars(
        select(ArticleDraft)
        .where(ArticleDraft.author_id == user.id)
        .order_by(ArticleDraft.updated_at.desc(), ArticleDraft.id.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).all()
    return PaginatedResponse[DraftListItem](
        count=count,
        next=(
            str(request.url.include_query_params(page=page + 1))
            if page * PAGE_SIZE < count
            else None
        ),
        previous=(
            str(request.url.include_query_params(page=page - 1))
            if page > 1 and count
            else None
        ),
        results=[
            DraftListItem(
                id=draft.id,
                title=draft.title,
                progress=_draft_progress(draft),
                article_id=draft.article_id,
                updated_at=draft.updated_at,
                last_auto_save=draft.last_auto_save,
            )
            for draft in drafts
        ],
    )


@router.get("/drafts/{draft_id}/", response_model=DraftDetail)
def get_draft(
    draft_id: int,
    user: CustomUser = Depends(get_verified_provider),
    db: Session = Depends(get_db),
) -> DraftDetail:
    draft = db.scalar(
        select(ArticleDraft).where(
            ArticleDraft.id == draft_id,
            ArticleDraft.author_id == user.id,
        )
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return _draft_detail(draft)


@router.delete("/drafts/{draft_id}/", response_model=MessageResponse)
def delete_draft(
    draft_id: int,
    user: CustomUser = Depends(get_verified_provider),
    db: Session = Depends(get_db),
) -> MessageResponse:
    draft = db.scalar(
        select(ArticleDraft).where(
            ArticleDraft.id == draft_id,
            ArticleDraft.author_id == user.id,
        )
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found.")
    db.delete(draft)
    db.commit()
    return MessageResponse(message="Draft deleted successfully.")


def _publish_draft_record(
    draft: ArticleDraft,
    user: CustomUser,
    db: Session,
) -> Article:
    errors = _publication_errors(draft)
    category = (
        db.get(Category, draft.category_id)
        if draft.category_id is not None
        else None
    )
    if draft.category_id is not None and (category is None or not category.is_active):
        errors["category_id"] = ["Select an active category."]
    if errors:
        _raise_validation_error(errors)

    if draft.article_id is not None:
        article = db.get(Article, draft.article_id)
        if article is None or article.author_id != user.id:
            raise HTTPException(status_code=404, detail="Draft article not found.")
        if article.status == ArticleStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=409,
                detail="Published articles must be submitted as revisions for staff review.",
            )
        article.title = draft.title.strip()
        article.summary = draft.summary.strip()
        article.body = draft.body.strip()
        article.category_id = draft.category_id
        article.featured_image = draft.featured_image
        article.status = ArticleStatus.PUBLISHED.value
        article.slug = _unique_article_slug(db, article.title, article.id)
        if article.published_at is None:
            article.published_at = datetime.now(timezone.utc)
        article.reading_time = max(1, (len(article.body.split()) + 199) // 200)
    else:
        article = Article(
            author_id=user.id,
            category_id=draft.category_id,
            title=draft.title.strip(),
            summary=draft.summary.strip(),
            body=draft.body.strip(),
            featured_image=draft.featured_image,
            status=ArticleStatus.PUBLISHED.value,
            slug=_unique_article_slug(db, draft.title),
            reading_time=max(1, (len(draft.body.split()) + 199) // 200),
            published_at=datetime.now(timezone.utc),
        )
        db.add(article)
    db.flush()
    db.delete(draft)
    return article


@router.post(
    "/drafts/{draft_id}/publish/",
    response_model=ArticlePublishResponse,
)
def publish_draft(
    draft_id: int,
    user: CustomUser = Depends(get_verified_provider),
    db: Session = Depends(get_db),
) -> ArticlePublishResponse:
    draft = db.scalar(
        select(ArticleDraft)
        .where(ArticleDraft.id == draft_id, ArticleDraft.author_id == user.id)
        .with_for_update()
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found.")
    article = _publish_draft_record(draft, user, db)
    db.commit()
    article = db.scalar(_article_query().where(Article.id == article.id))
    return ArticlePublishResponse(
        message="Article published successfully.",
        article=_article_detail(article, is_author=True),
    )


@router.get("/me/drafts/", response_model=PaginatedResponse[ArticleList])
def list_my_draft_articles(
    request: Request,
    page: int = Query(default=1, ge=1, le=10000),
    user: CustomUser = Depends(get_verified_provider),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ArticleList]:
    filters = (
        Article.author_id == user.id,
        Article.status == ArticleStatus.DRAFT.value,
    )
    count = db.scalar(select(func.count(Article.id)).where(*filters)) or 0
    articles = db.scalars(
        select(Article)
        .options(joinedload(Article.author), joinedload(Article.category))
        .where(*filters)
        .order_by(Article.updated_at.desc(), Article.id.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).unique().all()
    return PaginatedResponse[ArticleList](
        count=count,
        next=(
            str(request.url.include_query_params(page=page + 1))
            if page * PAGE_SIZE < count
            else None
        ),
        previous=(
            str(request.url.include_query_params(page=page - 1))
            if page > 1 and count
            else None
        ),
        results=[_article_list(article) for article in articles],
    )


@router.post("/{article_id}/edit-draft/", response_model=DraftResponse)
def create_article_edit_draft(
    article_id: int,
    user: CustomUser = Depends(get_verified_provider),
    db: Session = Depends(get_db),
) -> DraftResponse:
    article = db.scalar(
        select(Article).where(
            Article.id == article_id,
            Article.author_id == user.id,
            Article.status == ArticleStatus.PUBLISHED.value,
        )
    )
    if article is None:
        raise HTTPException(status_code=404, detail="Published article not found.")
    draft = db.scalar(select(ArticleDraft).where(ArticleDraft.article_id == article.id))
    if draft is None:
        draft = ArticleDraft(
            author_id=user.id,
            article_id=article.id,
            title=article.title,
            summary=article.summary,
            body=article.body,
            category_id=article.category_id,
            featured_image=article.featured_image,
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)
    return DraftResponse(draft=_draft_detail(draft))


@router.post("/drafts/{draft_id}/submit-revision/", response_model=ArticleRevisionResponse, status_code=status.HTTP_201_CREATED)
def submit_article_revision(
    draft_id: int,
    payload: ArticleRevisionCreate,
    user: CustomUser = Depends(get_verified_provider),
    db: Session = Depends(get_db),
) -> ArticleRevisionResponse:
    draft = db.scalar(
        select(ArticleDraft).where(
            ArticleDraft.id == draft_id,
            ArticleDraft.author_id == user.id,
        ).with_for_update()
    )
    if draft is None or draft.article_id is None:
        raise HTTPException(status_code=404, detail="Article edit draft not found.")
    article = db.scalar(
        select(Article).where(
            Article.id == draft.article_id,
            Article.author_id == user.id,
            Article.status == ArticleStatus.PUBLISHED.value,
        ).with_for_update()
    )
    if article is None:
        raise HTTPException(status_code=404, detail="Published article not found.")
    if (
        len(payload.title.strip()) < 10
        or len(payload.summary.strip()) < 20
        or len(payload.body.strip()) < 100
    ):
        _raise_validation_error({
            "content": ["Title, summary, and article text must meet the minimum length requirements."],
        })
    if len(payload.change_note.strip()) < 10:
        _raise_validation_error({"change_note": ["Explain the reason for this edit in at least 10 characters."]})
    category = db.get(Category, payload.category_id)
    if category is None or not category.is_active:
        _raise_validation_error({"category_id": ["Select an active category."]})
    pending = db.scalar(select(ArticleRevision.id).where(
        ArticleRevision.article_id == article.id,
        ArticleRevision.status == ArticleRevisionStatus.PENDING.value,
    ))
    if pending is not None:
        raise HTTPException(status_code=409, detail="An edit is already awaiting review for this article.")
    revision = ArticleRevision(
        article_id=article.id,
        author_id=user.id,
        title=payload.title.strip(),
        summary=payload.summary.strip(),
        body=payload.body.strip(),
        category_id=payload.category_id,
        featured_image=payload.featured_image,
        change_note=payload.change_note.strip(),
    )
    db.add(revision)
    db.delete(draft)
    db.commit()
    revision = db.scalar(
        select(ArticleRevision)
        .options(joinedload(ArticleRevision.article), joinedload(ArticleRevision.author))
        .where(ArticleRevision.id == revision.id)
    )
    return ArticleRevisionResponse(
        message="Your proposed changes were submitted for review. The published article remains unchanged until approval.",
        revision=_revision_read(revision),
    )


@router.get("/me/revisions/", response_model=PaginatedResponse[ArticleRevisionRead])
def list_my_article_revisions(
    request: Request,
    page: int = Query(default=1, ge=1, le=10000),
    user: CustomUser = Depends(get_verified_provider),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ArticleRevisionRead]:
    filters = (ArticleRevision.author_id == user.id,)
    count = db.scalar(select(func.count(ArticleRevision.id)).where(*filters)) or 0
    rows = db.scalars(
        select(ArticleRevision)
        .options(joinedload(ArticleRevision.article), joinedload(ArticleRevision.author))
        .where(*filters)
        .order_by(ArticleRevision.created_at.desc(), ArticleRevision.id.desc())
        .offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    ).unique().all()
    return PaginatedResponse[ArticleRevisionRead](
        count=count,
        next=str(request.url.include_query_params(page=page + 1)) if page * PAGE_SIZE < count else None,
        previous=str(request.url.include_query_params(page=page - 1)) if page > 1 and count else None,
        results=[_revision_read(row) for row in rows],
    )


@router.get("/revisions/review-queue/", response_model=PaginatedResponse[ArticleRevisionRead])
def list_article_review_queue(
    request: Request,
    page: int = Query(default=1, ge=1, le=10000),
    _staff: CustomUser = Depends(get_staff_user),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ArticleRevisionRead]:
    filters = (ArticleRevision.status == ArticleRevisionStatus.PENDING.value,)
    count = db.scalar(select(func.count(ArticleRevision.id)).where(*filters)) or 0
    rows = db.scalars(
        select(ArticleRevision)
        .options(joinedload(ArticleRevision.article), joinedload(ArticleRevision.author))
        .where(*filters)
        .order_by(ArticleRevision.created_at.asc(), ArticleRevision.id.asc())
        .offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    ).unique().all()
    return PaginatedResponse[ArticleRevisionRead](
        count=count,
        next=str(request.url.include_query_params(page=page + 1)) if page * PAGE_SIZE < count else None,
        previous=str(request.url.include_query_params(page=page - 1)) if page > 1 and count else None,
        results=[_revision_read(row) for row in rows],
    )


@router.patch("/revisions/{revision_id}/review/", response_model=ArticleRevisionResponse)
def review_article_revision(
    revision_id: int,
    payload: ArticleRevisionReview,
    reviewer: CustomUser = Depends(get_staff_user),
    db: Session = Depends(get_db),
) -> ArticleRevisionResponse:
    revision = db.scalar(
        select(ArticleRevision)
        .options(joinedload(ArticleRevision.article), joinedload(ArticleRevision.author))
        .where(ArticleRevision.id == revision_id)
        .with_for_update()
    )
    if revision is None:
        raise HTTPException(status_code=404, detail="Article revision not found.")
    if revision.status != ArticleRevisionStatus.PENDING.value:
        raise HTTPException(status_code=409, detail="This revision has already been reviewed.")
    if revision.author_id == reviewer.id:
        raise HTTPException(status_code=403, detail="Reviewers cannot approve their own article edits.")
    revision.status = payload.status
    revision.reviewer_id = reviewer.id
    revision.reviewer_note = payload.reviewer_note.strip() if payload.reviewer_note else None
    revision.reviewed_at = datetime.now(timezone.utc)
    if payload.status == ArticleRevisionStatus.APPROVED.value:
        article = revision.article
        previous_title = article.title
        category = db.get(Category, revision.category_id)
        if article.status != ArticleStatus.PUBLISHED.value:
            raise HTTPException(status_code=409, detail="The article is no longer published.")
        if category is None or not category.is_active:
            _raise_validation_error({"category_id": ["The proposed category is no longer active."]})
        revision.previous_title = article.title
        revision.previous_summary = article.summary
        revision.previous_body = article.body
        revision.previous_category_id = article.category_id
        revision.previous_featured_image = article.featured_image
        article.title = revision.title
        article.summary = revision.summary
        article.body = revision.body
        article.category_id = revision.category_id
        article.featured_image = revision.featured_image
        article.reading_time = max(1, (len(article.body.split()) + 199) // 200)
        article.updated_at = revision.reviewed_at
    db.commit()
    db.refresh(revision)
    return ArticleRevisionResponse(
        message="Proposed changes approved and published." if payload.status == "approved" else "Proposed changes rejected. The published article remains unchanged.",
        revision=_revision_read(revision),
    )


@router.delete("/{article_id}/", response_model=MessageResponse)
def delete_article(
    article_id: int,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found.")
    if article.author_id != user.id:
        raise HTTPException(status_code=403, detail="You do not own this article.")
    if article.status != ArticleStatus.DRAFT.value:
        raise HTTPException(
            status_code=400,
            detail="Only unpublished draft articles can be deleted.",
        )
    db.delete(article)
    db.commit()
    return MessageResponse(message="Draft article deleted successfully.")


@router.post("/{article_id}/publish/", response_model=ArticlePublishResponse)
def publish_article(
    article_id: int,
    user: CustomUser = Depends(get_verified_provider),
    db: Session = Depends(get_db),
) -> ArticlePublishResponse:
    article = db.scalar(
        select(Article)
        .where(Article.id == article_id, Article.author_id == user.id)
        .with_for_update()
    )
    if article is None:
        raise HTTPException(status_code=404, detail="Draft article not found.")
    if article.status != ArticleStatus.DRAFT.value:
        raise HTTPException(status_code=400, detail="Only draft articles can be published.")
    try:
        payload = ArticleDraft(
            author_id=user.id,
            title=article.title,
            summary=article.summary,
            body=article.body,
            category_id=article.category_id,
            featured_image=article.featured_image,
            article_id=article.id,
        )
        errors = _publication_errors(payload)
        if article.category is None or not article.category.is_active:
            errors["category_id"] = ["Select an active category."]
        if errors:
            _raise_validation_error(errors)
        article.status = ArticleStatus.PUBLISHED.value
        article.slug = _unique_article_slug(db, article.title, article.id)
        article.reading_time = max(1, (len(article.body.split()) + 199) // 200)
        if article.published_at is None:
            article.published_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        raise
    article = db.scalar(_article_query().where(Article.id == article_id))
    return ArticlePublishResponse(
        message="Article published successfully.",
        article=_article_detail(article, is_author=True),
    )


@router.get("/{slug}/", response_model=ArticleDetail)
def get_article(
    slug: str,
    user: CustomUser | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> ArticleDetail:
    article = db.scalar(_article_query().where(Article.slug == slug))
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found.")
    db.execute(
        update(Article)
        .where(Article.id == article.id)
        .values(view_count=Article.view_count + 1)
        .execution_options(synchronize_session="fetch")
    )
    db.commit()
    db.refresh(article)
    return _article_detail(article, is_author=user is not None and user.id == article.author_id)
