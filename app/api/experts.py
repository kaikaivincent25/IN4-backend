import re
import secrets
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.articles import _article_list
from app.core.dependencies import (
    get_current_user,
    get_staff_user,
    get_verified_provider,
)
from app.db.models.article import Article, ArticleStatus
from app.db.models.expert import Expert, ExpertBadgeTier, ExpertStatus
from app.db.models.user import CustomUser
from app.db.models.verification import ExpertVouch, VerificationDocument
from app.db.schemas.common import PaginatedResponse
from app.db.schemas.experts import (
    ExpertApplicationRequest,
    ExpertApplicationResponse,
    ExpertListItem,
    ExpertListQuery,
    ExpertProfileResponse,
    ExpertProfileUpdateRequest,
    ExpertProfileUpdateResponse,
    ExpertPublicProfile,
    ExpertRead,
    ExpertVerificationRequest,
    ExpertVerificationResponse,
)
from app.db.schemas.auth import MessageResponse
from app.db.session import get_db


router = APIRouter(prefix="/api/experts", tags=["experts"])
PAGE_SIZE = 20
_PRIVATE_DOCUMENTS = Path(__file__).resolve().parents[2] / "private_verification_documents"
_ALLOWED_DOCUMENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}
_MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
_PROFESSION_LABELS = {
    "doctor": "Doctor",
    "nurse": "Nurse",
    "lawyer": "Lawyer",
    "financial_advisor": "Financial Advisor",
    "other": "Other",
}
_BADGE_LABELS = {
    ExpertBadgeTier.VERIFIED.value: "Verified Expert",
    ExpertBadgeTier.CREDENTIALLED.value: "Credentialed Expert",
    ExpertBadgeTier.INSTITUTIONAL.value: "Institutional Expert",
}


def _display_profession(profession: str) -> str:
    return _PROFESSION_LABELS.get(profession, profession.replace("_", " ").title())


def _expert_read(expert: Expert) -> ExpertRead:
    return ExpertRead(
        id=expert.id,
        user_id=expert.user_id,
        profession=expert.profession,
        license_number=expert.license_number,
        license_issuer=expert.license_issuer,
        bio=expert.bio,
        expertise_areas=expert.expertise_areas,
        organization=expert.organization,
        location=expert.location,
        languages=expert.languages,
        consultation_methods=expert.consultation_methods,
        status=expert.status,
        badge_tier=expert.badge_tier,
        verified_by_id=expert.verified_by_id,
        verified_at=expert.verified_at,
        rejection_reason=expert.rejection_reason,
        slug=expert.slug,
        is_verified=expert.status == ExpertStatus.VERIFIED.value,
        created_at=expert.created_at,
        updated_at=expert.updated_at,
    )


def _expert_list_item(expert: Expert) -> ExpertListItem:
    published_count = sum(
        article.status == ArticleStatus.PUBLISHED.value
        for article in expert.user.articles
    )
    return ExpertListItem(
        id=expert.id,
        slug=expert.slug,
        name=" ".join(
            part for part in (expert.user.first_name, expert.user.last_name) if part
        )
        or expert.user.email,
        profile_image=expert.user.profile_image,
        profession=expert.profession,
        profession_display=_display_profession(expert.profession),
        bio=expert.bio,
        organization=expert.organization,
        location=expert.location,
        badge_tier=expert.badge_tier,
        badge_display=_BADGE_LABELS.get(expert.badge_tier, expert.badge_tier.title()),
        article_count=published_count,
        verified_at=expert.verified_at,
    )


def _slug_base(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "expert"


def _unique_slug(db: Session, base: str) -> str:
    slug = base
    suffix = 2
    while db.scalar(select(Expert.id).where(Expert.slug == slug)) is not None:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


@router.get("/", response_model=PaginatedResponse[ExpertListItem])
def list_experts(
    request: Request,
    query: ExpertListQuery = Depends(),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ExpertListItem]:
    filters = [Expert.status == ExpertStatus.VERIFIED.value]
    if query.profession:
        filters.append(Expert.profession == query.profession)
    if query.search:
        term = f"%{query.search.strip()}%"
        filters.append(
            or_(
                Expert.profession.ilike(term),
                Expert.bio.ilike(term),
                Expert.expertise_areas.ilike(term),
                Expert.organization.ilike(term),
                Expert.location.ilike(term),
                CustomUser.first_name.ilike(term),
                CustomUser.last_name.ilike(term),
            )
        )
    count = db.scalar(
        select(func.count(Expert.id))
        .join(CustomUser, Expert.user_id == CustomUser.id)
        .where(*filters)
    ) or 0
    experts = db.scalars(
        select(Expert)
        .join(CustomUser, Expert.user_id == CustomUser.id)
        .options(joinedload(Expert.user).selectinload(CustomUser.articles))
        .where(*filters)
        .order_by(Expert.verified_at.desc(), Expert.id.desc())
        .offset((query.page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).unique().all()
    return PaginatedResponse[ExpertListItem](
        count=count,
        next=(
            str(request.url.include_query_params(page=query.page + 1))
            if query.page * PAGE_SIZE < count
            else None
        ),
        previous=(
            str(request.url.include_query_params(page=query.page - 1))
            if query.page > 1 and count
            else None
        ),
        results=[_expert_list_item(expert) for expert in experts],
    )


@router.post(
    "/apply/",
    response_model=ExpertApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def apply_as_expert(
    payload: ExpertApplicationRequest,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExpertApplicationResponse:
    if db.scalar(select(Expert.id).where(Expert.user_id == user.id)) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An expert application already exists for this account.",
        )

    name = " ".join(part for part in (user.first_name, user.last_name) if part)
    expert = Expert(
        user_id=user.id,
        profession=payload.profession.strip(),
        license_number=payload.license_number.strip(),
        license_issuer=payload.license_issuer.strip(),
        bio=payload.bio,
        expertise_areas=payload.expertise_areas,
        organization=payload.organization,
        location=payload.location,
        languages=payload.languages,
        consultation_methods=payload.consultation_methods,
        status=ExpertStatus.PENDING.value,
        badge_tier=ExpertBadgeTier.VERIFIED.value,
        slug=_unique_slug(db, _slug_base(name or payload.profession)),
    )
    db.add(expert)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(expert)
    return ExpertApplicationResponse(
        message="Expert application submitted.",
        expert_id=expert.id,
    )


@router.post("/{expert_id}/documents/", status_code=status.HTTP_201_CREATED)
async def upload_verification_document(
    expert_id: int,
    file: UploadFile = File(...),
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    expert = db.scalar(select(Expert).where(Expert.id == expert_id, Expert.user_id == user.id))
    if expert is None:
        raise HTTPException(status_code=404, detail="Expert application not found.")
    if expert.status == ExpertStatus.VERIFIED.value:
        raise HTTPException(status_code=400, detail="Verified applications cannot add review documents.")
    if file.content_type not in _ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(status_code=400, detail="Upload a PDF, JPEG, or PNG document.")
    content = await file.read(_MAX_DOCUMENT_BYTES + 1)
    if not content or len(content) > _MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail="Each document must be smaller than 10 MB.")
    signatures = {
        "application/pdf": content.startswith(b"%PDF-"),
        "image/jpeg": content.startswith(b"\xff\xd8\xff"),
        "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
    }
    if not signatures.get(file.content_type, False):
        raise HTTPException(status_code=400, detail="The file content does not match its document type.")
    key = secrets.token_hex(24)
    _PRIVATE_DOCUMENTS.mkdir(parents=True, exist_ok=True)
    (_PRIVATE_DOCUMENTS / key).write_bytes(content)
    document = VerificationDocument(
        expert_id=expert.id,
        original_name=Path(file.filename or "document").name[:255],
        content_type=file.content_type,
        storage_key=key,
    )
    db.add(document)
    db.commit()
    return {"status": "success", "document_id": document.id, "message": "Verification document uploaded."}


@router.get("/{expert_id}/documents/{document_id}/")
def download_verification_document(
    expert_id: int,
    document_id: int,
    staff_user: CustomUser = Depends(get_staff_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    document = db.scalar(select(VerificationDocument).where(
        VerificationDocument.id == document_id,
        VerificationDocument.expert_id == expert_id,
    ))
    if document is None:
        raise HTTPException(status_code=404, detail="Verification document not found.")
    path = _PRIVATE_DOCUMENTS / document.storage_key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Verification document file is unavailable.")
    return FileResponse(path, media_type=document.content_type, filename=document.original_name)


@router.get("/{expert_id}/documents/")
def list_verification_documents(
    expert_id: int,
    staff_user: CustomUser = Depends(get_staff_user),
    db: Session = Depends(get_db),
) -> dict[str, list[dict[str, str | int]]]:
    documents = db.scalars(select(VerificationDocument).where(
        VerificationDocument.expert_id == expert_id,
    ).order_by(VerificationDocument.uploaded_at)).all()
    return {"documents": [{
        "id": document.id,
        "filename": document.original_name,
        "content_type": document.content_type,
        "uploaded_at": document.uploaded_at.isoformat(),
    } for document in documents]}


@router.post("/{expert_id}/vouches/", status_code=status.HTTP_201_CREATED)
def vouch_for_expert(
    expert_id: int,
    payload: dict,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    expert = db.get(Expert, expert_id)
    if expert is None:
        raise HTTPException(status_code=404, detail="Professional profile not found.")
    if expert.user_id == user.id:
        raise HTTPException(status_code=400, detail="You cannot vouch for your own profile.")
    relationship_type = str(payload.get("relationship_type", "")).strip()
    note = str(payload.get("note", "")).strip() or None
    if not relationship_type or len(relationship_type) > 80 or (note and len(note) > 500):
        raise HTTPException(status_code=400, detail="Provide a relationship (up to 80 characters) and note (up to 500 characters).")
    if db.scalar(select(ExpertVouch.id).where(ExpertVouch.expert_id == expert_id, ExpertVouch.vouched_by_id == user.id)):
        raise HTTPException(status_code=409, detail="You have already vouched for this professional.")
    vouch = ExpertVouch(expert_id=expert_id, vouched_by_id=user.id, relationship_type=relationship_type, note=note)
    db.add(vouch)
    db.commit()
    return {"status": "success", "vouch_id": vouch.id, "message": "Your vouch has been recorded."}


@router.get("/me/", response_model=ExpertProfileResponse)
def get_my_expert_profile(
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExpertProfileResponse:
    expert = db.scalar(select(Expert).where(Expert.user_id == user.id))
    if expert is None:
        raise HTTPException(status_code=404, detail="Expert profile not found.")
    return ExpertProfileResponse(expert=_expert_read(expert))


@router.put("/me/", response_model=ExpertProfileUpdateResponse)
def update_my_expert_profile(
    payload: ExpertProfileUpdateRequest,
    user: CustomUser = Depends(get_verified_provider),
    db: Session = Depends(get_db),
) -> ExpertProfileUpdateResponse:
    expert = db.scalar(select(Expert).where(Expert.user_id == user.id))
    if expert is None:
        raise HTTPException(status_code=404, detail="Expert profile not found.")
    for field in ("bio", "expertise_areas", "organization", "location", "languages", "consultation_methods"):
        if field in payload.model_fields_set:
            setattr(expert, field, getattr(payload, field))
    db.commit()
    db.refresh(expert)
    return ExpertProfileUpdateResponse(
        message="Expert profile updated.",
        expert=_expert_read(expert),
    )


@router.patch("/{expert_id}/verify/", response_model=ExpertVerificationResponse)
def verify_expert(
    expert_id: int,
    payload: ExpertVerificationRequest,
    staff_user: CustomUser = Depends(get_staff_user),
    db: Session = Depends(get_db),
) -> ExpertVerificationResponse:
    expert = db.get(Expert, expert_id)
    if expert is None:
        raise HTTPException(status_code=404, detail="Expert application not found.")
    if payload.status == ExpertStatus.VERIFIED.value and db.scalar(
        select(func.count(VerificationDocument.id)).where(VerificationDocument.expert_id == expert.id)
    ) == 0:
        raise HTTPException(status_code=400, detail="At least one supporting document is required before verification.")
    expert.status = payload.status
    expert.verified_by_id = staff_user.id
    expert.verified_at = (
        datetime.now(timezone.utc)
        if payload.status == ExpertStatus.VERIFIED.value
        else None
    )
    expert.rejection_reason = (
        payload.rejection_reason
        if payload.status == ExpertStatus.REJECTED.value
        else None
    )
    if payload.badge_tier is not None:
        expert.badge_tier = payload.badge_tier.value
    user = db.get(CustomUser, expert.user_id)
    user.is_provider = payload.status == ExpertStatus.VERIFIED.value
    db.commit()
    db.refresh(expert)
    return ExpertVerificationResponse(
        message="Expert verification updated.",
        expert=_expert_read(expert),
    )


@router.get("/{slug}/", response_model=ExpertPublicProfile)
def get_expert_profile(slug: str, db: Session = Depends(get_db)) -> ExpertPublicProfile:
    expert = db.scalar(
        select(Expert)
        .join(CustomUser, Expert.user_id == CustomUser.id)
        .options(
            joinedload(Expert.user).selectinload(CustomUser.articles).joinedload(Article.category),
        )
        .where(
            Expert.slug == slug,
            Expert.status == ExpertStatus.VERIFIED.value,
        )
    )
    if expert is None:
        raise HTTPException(status_code=404, detail="Expert not found.")

    published_articles = [
        article
        for article in expert.user.articles
        if article.status == ArticleStatus.PUBLISHED.value
    ]
    published_articles.sort(
        key=lambda article: (article.published_at is not None, article.published_at, article.id),
        reverse=True,
    )
    badge = _BADGE_LABELS.get(expert.badge_tier, expert.badge_tier.title())
    vouches = db.scalars(select(ExpertVouch).where(ExpertVouch.expert_id == expert.id).options(
        joinedload(ExpertVouch.vouched_by),
    ).order_by(ExpertVouch.created_at.desc())).all()
    return ExpertPublicProfile(
        id=expert.id,
        slug=expert.slug,
        name=" ".join(
            part
            for part in (expert.user.first_name, expert.user.last_name)
            if part
        )
        or expert.user.email,
        profile_image=expert.user.profile_image,
        profession=expert.profession,
        profession_display=_display_profession(expert.profession),
        bio=expert.bio,
        expertise_areas=expert.expertise_areas,
        organization=expert.organization,
        location=expert.location,
        languages=expert.languages,
        consultation_methods=expert.consultation_methods,
        badge_tier=expert.badge_tier,
        badge_display=badge,
        article_count=len(published_articles),
        verified_at=expert.verified_at,
        vouch_count=len(vouches),
        vouches=[{
            "name": " ".join(part for part in (v.vouched_by.first_name, v.vouched_by.last_name) if part) or "IN4 member",
            "relationship_type": v.relationship_type,
            "note": v.note,
            "created_at": v.created_at,
        } for v in vouches],
        articles=[_article_list(article) for article in published_articles],
    )
