from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_current_user
from app.db.models.article import Article, ArticleStatus
from app.db.models.community import ArticleComment, Conversation, ConversationMessage, ExpertProfileComment
from app.db.models.engagement import ReadHistory
from app.db.models.expert import Expert, ExpertStatus
from app.db.models.user import CustomUser
from app.db.schemas.community import (
    CommentCreate,
    CommentRead,
    ExpertCommentEligibility,
    ExpertProfileCommentCreate,
    ExpertProfileCommentRead,
    ConversationCreate,
    ConversationMessages,
    ConversationRead,
    MessageCreate,
    MessageRead,
)
from app.db.schemas.common import PaginatedResponse
from app.db.schemas.auth import MessageResponse
from app.db.session import get_db


router = APIRouter(prefix="/api/community", tags=["community"])


def _published_article(db: Session, article_id: int) -> Article:
    article = db.scalar(
        select(Article)
        .options(joinedload(Article.author))
        .where(Article.id == article_id, Article.status == ArticleStatus.PUBLISHED.value)
    )
    if article is None:
        raise HTTPException(status_code=404, detail="Published article not found.")
    return article


def _display_name(user: CustomUser) -> str:
    return " ".join(part for part in (user.first_name, user.last_name) if part) or user.email


def _comment_read(comment: ArticleComment) -> CommentRead:
    return CommentRead(
        id=comment.id,
        article_id=comment.article_id,
        user_id=comment.user_id,
        author_name=_display_name(comment.author),
        content=comment.content,
        created_at=comment.created_at,
    )


def _expert_profile_comment_read(comment: ExpertProfileComment) -> ExpertProfileCommentRead:
    return ExpertProfileCommentRead(
        id=comment.id,
        expert_id=comment.expert_id,
        user_id=comment.user_id,
        author_name=_display_name(comment.author),
        content=comment.content,
        created_at=comment.created_at,
    )


def _verified_expert(db: Session, slug: str) -> Expert:
    expert = db.scalar(
        select(Expert).where(
            Expert.slug == slug,
            Expert.status == ExpertStatus.VERIFIED.value,
        )
    )
    if expert is None:
        raise HTTPException(status_code=404, detail="Verified expert not found.")
    return expert


def _read_article_count(db: Session, expert: Expert, user_id: int) -> int:
    return db.scalar(
        select(func.count(ReadHistory.id))
        .join(Article, ReadHistory.article_id == Article.id)
        .where(
            ReadHistory.user_id == user_id,
            Article.author_id == expert.user_id,
            Article.status == ArticleStatus.PUBLISHED.value,
        )
    ) or 0


@router.get("/experts/{slug}/comments/", response_model=PaginatedResponse[ExpertProfileCommentRead])
def list_expert_profile_comments(
    slug: str,
    page: int = Query(default=1, ge=1, le=10000),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ExpertProfileCommentRead]:
    expert = _verified_expert(db, slug)
    count = db.scalar(
        select(func.count(ExpertProfileComment.id)).where(ExpertProfileComment.expert_id == expert.id)
    ) or 0
    comments = db.scalars(
        select(ExpertProfileComment)
        .options(joinedload(ExpertProfileComment.author))
        .where(ExpertProfileComment.expert_id == expert.id)
        .order_by(ExpertProfileComment.created_at.desc(), ExpertProfileComment.id.desc())
        .offset((page - 1) * 30)
        .limit(30)
    ).unique().all()
    return PaginatedResponse[ExpertProfileCommentRead](
        count=count,
        next=f"/api/community/experts/{slug}/comments/?page={page + 1}" if page * 30 < count else None,
        previous=f"/api/community/experts/{slug}/comments/?page={page - 1}" if page > 1 and count else None,
        results=[_expert_profile_comment_read(comment) for comment in comments],
    )


@router.get("/experts/{slug}/comments/eligibility/", response_model=ExpertCommentEligibility)
def get_expert_comment_eligibility(
    slug: str,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExpertCommentEligibility:
    expert = _verified_expert(db, slug)
    read_count = _read_article_count(db, expert, user.id)
    already_commented = db.scalar(
        select(ExpertProfileComment.id).where(
            ExpertProfileComment.expert_id == expert.id,
            ExpertProfileComment.user_id == user.id,
        )
    ) is not None
    return ExpertCommentEligibility(
        can_comment=user.id != expert.user_id and read_count > 0 and not already_commented,
        read_article_count=read_count,
        already_commented=already_commented,
        is_profile_owner=user.id == expert.user_id,
    )


@router.post(
    "/experts/{slug}/comments/",
    response_model=ExpertProfileCommentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_expert_profile_comment(
    slug: str,
    payload: ExpertProfileCommentCreate,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExpertProfileCommentRead:
    expert = _verified_expert(db, slug)
    if user.id == expert.user_id:
        raise HTTPException(status_code=400, detail="You cannot comment on your own expert profile.")
    if _read_article_count(db, expert, user.id) == 0:
        raise HTTPException(status_code=403, detail="Read at least one of this expert's published articles before commenting.")
    comment = ExpertProfileComment(expert_id=expert.id, user_id=user.id, content=payload.content.strip())
    if not comment.content:
        raise HTTPException(status_code=400, detail="A comment cannot be empty.")
    db.add(comment)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="You have already commented on this expert profile.") from exc
    db.refresh(comment)
    comment.author = user
    return _expert_profile_comment_read(comment)


@router.delete("/expert-comments/{comment_id}/", response_model=MessageResponse)
def delete_expert_profile_comment(
    comment_id: int,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    comment = db.scalar(
        select(ExpertProfileComment)
        .options(joinedload(ExpertProfileComment.expert))
        .where(ExpertProfileComment.id == comment_id)
    )
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found.")
    if comment.user_id != user.id and comment.expert.user_id != user.id and not user.is_staff:
        raise HTTPException(status_code=403, detail="You cannot remove this comment.")
    db.delete(comment)
    db.commit()
    return MessageResponse(message="Comment removed.")


def _conversation_read(conversation: Conversation, current_user_id: int, db: Session) -> ConversationRead:
    other = conversation.expert if current_user_id == conversation.reader_id else conversation.reader
    other_is_expert = current_user_id == conversation.reader_id
    other_expert_profile = other.expert_profile if other_is_expert else None
    other_verified = bool(
        other_expert_profile
        and other_expert_profile.status == ExpertStatus.VERIFIED.value
    )
    last = db.scalar(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation.id)
        .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
        .limit(1)
    )
    return ConversationRead(
        id=conversation.id,
        article_id=conversation.article_id,
        article_title=conversation.article.title,
        article_slug=conversation.article.slug,
        other_user_id=other.id,
        other_user_name=_display_name(other),
        other_user_profile_image=other.profile_image,
        other_user_is_expert=other_is_expert,
        other_user_verified=other_verified,
        other_user_badge_tier=other_expert_profile.badge_tier if other_verified else None,
        last_message=last.content if last else None,
        last_message_at=last.created_at if last else None,
        updated_at=conversation.updated_at,
        article_category_name=conversation.article.category.name if conversation.article.category else None,
    )


def _message_read(message: ConversationMessage) -> MessageRead:
    return MessageRead(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        sender_name=_display_name(message.sender),
        content=message.content,
        created_at=message.created_at,
    )


@router.get("/articles/{article_id}/comments/", response_model=PaginatedResponse[CommentRead])
def list_article_comments(
    article_id: int,
    page: int = Query(default=1, ge=1, le=10000),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CommentRead]:
    _published_article(db, article_id)
    count = db.query(ArticleComment.id).filter(ArticleComment.article_id == article_id).count()
    comments = db.scalars(
        select(ArticleComment)
        .options(joinedload(ArticleComment.author))
        .where(ArticleComment.article_id == article_id)
        .order_by(ArticleComment.created_at.desc(), ArticleComment.id.desc())
        .offset((page - 1) * 30).limit(30)
    ).unique().all()
    return PaginatedResponse[CommentRead](
        count=count,
        next=f"/api/community/articles/{article_id}/comments/?page={page + 1}" if page * 30 < count else None,
        previous=f"/api/community/articles/{article_id}/comments/?page={page - 1}" if page > 1 and count else None,
        results=[_comment_read(comment) for comment in comments],
    )


@router.post("/articles/{article_id}/comments/", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
def create_article_comment(
    article_id: int,
    payload: CommentCreate,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentRead:
    _published_article(db, article_id)
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="A comment cannot be empty.")
    comment = ArticleComment(article_id=article_id, user_id=user.id, content=content)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    comment.author = user
    return _comment_read(comment)


@router.delete("/comments/{comment_id}/", response_model=MessageResponse)
def delete_comment(
    comment_id: int,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    comment = db.scalar(
        select(ArticleComment)
        .options(joinedload(ArticleComment.article))
        .where(ArticleComment.id == comment_id)
    )
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found.")
    if comment.user_id != user.id and comment.article.author_id != user.id and not user.is_staff:
        raise HTTPException(status_code=403, detail="You cannot remove this comment.")
    db.delete(comment)
    db.commit()
    return MessageResponse(message="Comment removed.")


@router.post("/conversations/", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def start_conversation(
    payload: ConversationCreate,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationRead:
    article = _published_article(db, payload.article_id)
    if article.author_id == user.id:
        raise HTTPException(status_code=400, detail="You cannot start a conversation with yourself.")
    if article.author.is_provider is False:
        raise HTTPException(status_code=409, detail="This article's author is not currently available for expert messaging.")
    conversation = db.scalar(
        select(Conversation)
        .options(
            joinedload(Conversation.article).joinedload(Article.category),
            joinedload(Conversation.reader).joinedload(CustomUser.expert_profile),
            joinedload(Conversation.expert).joinedload(CustomUser.expert_profile),
        )
        .where(
            Conversation.article_id == article.id,
            Conversation.reader_id == user.id,
            Conversation.expert_id == article.author_id,
        )
    )
    if conversation is None:
        conversation = Conversation(article_id=article.id, reader_id=user.id, expert_id=article.author_id)
        db.add(conversation)
        try:
            db.commit()
            db.refresh(conversation)
        except IntegrityError:
            db.rollback()
            conversation = db.scalar(
                select(Conversation)
                .options(
                    joinedload(Conversation.article).joinedload(Article.category),
                    joinedload(Conversation.reader).joinedload(CustomUser.expert_profile),
                    joinedload(Conversation.expert).joinedload(CustomUser.expert_profile),
                )
                .where(
                    Conversation.article_id == article.id,
                    Conversation.reader_id == user.id,
                    Conversation.expert_id == article.author_id,
                )
            )
            if conversation is None:
                raise
    return _conversation_read(conversation, user.id, db)


@router.get("/conversations/", response_model=list[ConversationRead])
def list_conversations(
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConversationRead]:
    conversations = db.scalars(
        select(Conversation)
        .options(
            joinedload(Conversation.article).joinedload(Article.category),
            joinedload(Conversation.reader).joinedload(CustomUser.expert_profile),
            joinedload(Conversation.expert).joinedload(CustomUser.expert_profile),
        )
        .where(or_(Conversation.reader_id == user.id, Conversation.expert_id == user.id))
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
    ).unique().all()
    return [_conversation_read(conversation, user.id, db) for conversation in conversations]


def _get_participant_conversation(db: Session, conversation_id: int, user_id: int) -> Conversation:
    conversation = db.scalar(
        select(Conversation)
        .options(
            joinedload(Conversation.article).joinedload(Article.category),
            joinedload(Conversation.reader).joinedload(CustomUser.expert_profile),
            joinedload(Conversation.expert).joinedload(CustomUser.expert_profile),
        )
        .where(
            Conversation.id == conversation_id,
            or_(Conversation.reader_id == user_id, Conversation.expert_id == user_id),
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation


@router.get("/conversations/{conversation_id}/messages/", response_model=ConversationMessages)
def list_messages(
    conversation_id: int,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationMessages:
    conversation = _get_participant_conversation(db, conversation_id, user.id)
    messages = db.scalars(
        select(ConversationMessage)
        .options(joinedload(ConversationMessage.sender))
        .where(ConversationMessage.conversation_id == conversation.id)
        .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
        .limit(100)
    ).unique().all()
    messages.reverse()
    return ConversationMessages(
        conversation=_conversation_read(conversation, user.id, db),
        messages=[_message_read(message) for message in messages],
    )


@router.post("/conversations/{conversation_id}/messages/", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
def send_message(
    conversation_id: int,
    payload: MessageCreate,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageRead:
    conversation = _get_participant_conversation(db, conversation_id, user.id)
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="A message cannot be empty.")
    message = ConversationMessage(conversation_id=conversation.id, sender_id=user.id, content=content)
    conversation.updated_at = datetime.now(timezone.utc)
    db.add(message)
    db.commit()
    db.refresh(message)
    message.sender = user
    return _message_read(message)
