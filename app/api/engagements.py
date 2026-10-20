from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.articles import _article_list
from app.core.dependencies import get_current_user
from app.db.models.article import Article, ArticleStatus
from app.db.models.engagement import ArticleStats, ReadHistory, SavedArticle
from app.db.models.user import CustomUser
from app.db.schemas.common import PaginatedResponse
from app.db.schemas.engagements import (
    ArticleIdRequest,
    ArticleStatsRead,
    EngagementMessageResponse,
    EngagementResponse,
    ReadHistoryRead,
    SavedArticleRead,
    SavedCountResponse,
    SavedStatusResponse,
)
from app.db.session import get_db


router = APIRouter(prefix="/api/engagements", tags=["engagements"])
PAGE_SIZE = 20


def _published_article(article_id: int, db: Session) -> Article:
    article = db.scalar(
        select(Article)
        .options(
            joinedload(Article.author).joinedload(CustomUser.expert_profile),
            joinedload(Article.category),
        )
        .where(
            Article.id == article_id,
            Article.status == ArticleStatus.PUBLISHED.value,
        )
    )
    if article is None:
        raise HTTPException(status_code=404, detail="Published article not found.")
    return article


def _sync_article_stats(article: Article, db: Session) -> ArticleStats:
    total_saves = db.scalar(
        select(func.count(SavedArticle.id)).where(SavedArticle.article_id == article.id)
    ) or 0
    total_reads = db.scalar(
        select(func.count(ReadHistory.id)).where(ReadHistory.article_id == article.id)
    ) or 0
    stats = db.scalar(
        select(ArticleStats)
        .where(ArticleStats.article_id == article.id)
        .with_for_update()
    )
    if stats is None:
        stats = ArticleStats(article_id=article.id)
        db.add(stats)
    stats.total_saves = total_saves
    stats.total_reads = total_reads
    stats.unique_readers = total_reads
    stats.engagement_score = total_saves + total_reads
    article.save_count = total_saves
    return stats


@router.post(
    "/saved/save/",
    response_model=EngagementResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_article(
    payload: ArticleIdRequest,
    response: Response,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EngagementResponse:
    article = _published_article(payload.article_id, db)
    existing = db.scalar(
        select(SavedArticle).where(
            SavedArticle.user_id == user.id,
            SavedArticle.article_id == article.id,
        )
    )
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return EngagementResponse(
            status="info",
            message="Article is already saved.",
            saved_article=SavedArticleRead(
                id=existing.id,
                article=_article_list(article),
                saved_at=existing.saved_at,
            ),
        )

    saved = SavedArticle(user_id=user.id, article_id=article.id)
    db.add(saved)
    try:
        db.flush()
        _sync_article_stats(article, db)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(SavedArticle).where(
                SavedArticle.user_id == user.id,
                SavedArticle.article_id == article.id,
            )
        )
        if existing is None:
            raise
        response.status_code = status.HTTP_200_OK
        saved = existing
    db.refresh(saved)
    return EngagementResponse(
        message="Article saved successfully.",
        saved_article=SavedArticleRead(
            id=saved.id,
            article=_article_list(article),
            saved_at=saved.saved_at,
        ),
    )


@router.post("/saved/unsave/", response_model=EngagementMessageResponse)
def unsave_article(
    payload: ArticleIdRequest,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EngagementMessageResponse:
    article = _published_article(payload.article_id, db)
    saved = db.scalar(
        select(SavedArticle)
        .where(
            SavedArticle.user_id == user.id,
            SavedArticle.article_id == article.id,
        )
        .with_for_update()
    )
    if saved is None:
        return EngagementMessageResponse(
            status="info",
            message="Article was not in the reading list.",
        )
    db.delete(saved)
    _sync_article_stats(article, db)
    db.commit()
    return EngagementMessageResponse(message="Article removed from the reading list.")


@router.get("/saved/", response_model=PaginatedResponse[SavedArticleRead])
def list_saved_articles(
    request: Request,
    page: int = 1,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SavedArticleRead]:
    if page < 1 or page > 10000:
        raise HTTPException(
            status_code=400,
            detail={"message": "Validation failed.", "errors": {"page": ["Page must be between 1 and 10000."]}},
        )
    filters = (
        SavedArticle.user_id == user.id,
        Article.status == ArticleStatus.PUBLISHED.value,
    )
    count = db.scalar(
        select(func.count(SavedArticle.id))
        .join(Article, SavedArticle.article_id == Article.id)
        .where(*filters)
    ) or 0
    records = db.scalars(
        select(SavedArticle)
        .join(Article, SavedArticle.article_id == Article.id)
        .options(
            joinedload(SavedArticle.article)
            .joinedload(Article.author)
            .joinedload(CustomUser.expert_profile),
            joinedload(SavedArticle.article).joinedload(Article.category),
        )
        .where(*filters)
        .order_by(SavedArticle.saved_at.desc(), SavedArticle.id.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).unique().all()
    return PaginatedResponse[SavedArticleRead](
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
            SavedArticleRead(
                id=record.id,
                article=_article_list(record.article),
                saved_at=record.saved_at,
            )
            for record in records
        ],
    )


@router.get("/saved/count/", response_model=SavedCountResponse)
def saved_count(
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SavedCountResponse:
    count = db.scalar(
        select(func.count(SavedArticle.id))
        .join(Article, SavedArticle.article_id == Article.id)
        .where(
            SavedArticle.user_id == user.id,
            Article.status == ArticleStatus.PUBLISHED.value,
        )
    ) or 0
    return SavedCountResponse(saved_count=count)


@router.get("/saved/check/", response_model=SavedStatusResponse)
def check_saved(
    article_id: int,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SavedStatusResponse:
    article = _published_article(article_id, db)
    exists = db.scalar(
        select(SavedArticle.id).where(
            SavedArticle.user_id == user.id,
            SavedArticle.article_id == article.id,
        )
    )
    return SavedStatusResponse(is_saved=exists is not None)


@router.post(
    "/history/record/",
    response_model=EngagementMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_read(
    payload: ArticleIdRequest,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EngagementMessageResponse:
    article = _published_article(payload.article_id, db)
    history = db.scalar(
        select(ReadHistory)
        .where(
            ReadHistory.user_id == user.id,
            ReadHistory.article_id == article.id,
        )
        .with_for_update()
    )
    created = history is None
    now = datetime.now(timezone.utc)
    if created:
        history = ReadHistory(
            user_id=user.id,
            article_id=article.id,
            read_at=now,
        )
        db.add(history)
        db.flush()
    else:
        history.read_at = now
    _sync_article_stats(article, db)
    db.commit()
    return EngagementMessageResponse(
        message="Read history recorded." if created else "Read history updated."
    )


@router.get("/history/", response_model=PaginatedResponse[ReadHistoryRead])
def list_read_history(
    request: Request,
    page: int = 1,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ReadHistoryRead]:
    if page < 1 or page > 10000:
        raise HTTPException(
            status_code=400,
            detail={"message": "Validation failed.", "errors": {"page": ["Page must be between 1 and 10000."]}},
        )
    filters = (
        ReadHistory.user_id == user.id,
        Article.status == ArticleStatus.PUBLISHED.value,
    )
    count = db.scalar(
        select(func.count(ReadHistory.id))
        .join(Article, ReadHistory.article_id == Article.id)
        .where(*filters)
    ) or 0
    records = db.scalars(
        select(ReadHistory)
        .join(Article, ReadHistory.article_id == Article.id)
        .options(
            joinedload(ReadHistory.article)
            .joinedload(Article.author)
            .joinedload(CustomUser.expert_profile),
            joinedload(ReadHistory.article).joinedload(Article.category),
        )
        .where(*filters)
        .order_by(ReadHistory.read_at.desc(), ReadHistory.id.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).unique().all()
    return PaginatedResponse[ReadHistoryRead](
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
            ReadHistoryRead(
                id=record.id,
                article=_article_list(record.article),
                read_at=record.read_at,
            )
            for record in records
        ],
    )


@router.get("/stats/", response_model=PaginatedResponse[ArticleStatsRead])
def list_public_stats(
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db),
) -> PaginatedResponse[ArticleStatsRead]:
    if page < 1 or page > 10000:
        raise HTTPException(
            status_code=400,
            detail={"message": "Validation failed.", "errors": {"page": ["Page must be between 1 and 10000."]}},
        )
    filters = Article.status == ArticleStatus.PUBLISHED.value
    count = db.scalar(
        select(func.count(ArticleStats.id))
        .join(Article, ArticleStats.article_id == Article.id)
        .where(filters)
    ) or 0
    stats = db.scalars(
        select(ArticleStats)
        .join(Article, ArticleStats.article_id == Article.id)
        .where(filters)
        .order_by(ArticleStats.engagement_score.desc(), ArticleStats.article_id)
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).all()
    return PaginatedResponse[ArticleStatsRead](
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
        results=[ArticleStatsRead.model_validate(row) for row in stats],
    )


@router.get("/stats/{article_id}/", response_model=ArticleStatsRead)
def get_public_stats(
    article_id: int,
    db: Session = Depends(get_db),
) -> ArticleStatsRead:
    stats = db.scalar(
        select(ArticleStats)
        .join(Article, ArticleStats.article_id == Article.id)
        .where(
            ArticleStats.article_id == article_id,
            Article.status == ArticleStatus.PUBLISHED.value,
        )
    )
    if stats is None:
        raise HTTPException(status_code=404, detail="Article statistics not found.")
    return ArticleStatsRead.model_validate(stats)
