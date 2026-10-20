import secrets
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_verified_provider
from app.core.config import settings
from app.db.models.user import CustomUser
from app.db.session import get_db


router = APIRouter(prefix="/api/media", tags=["media"])
MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_TYPES = {
    "image/jpeg": ("jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
    "image/png": ("png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    "image/webp": ("webp", lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"),
}


async def _save_image(file: UploadFile, bucket_name: str, folder: str, prefix: str) -> str:
    image_type = IMAGE_TYPES.get(file.content_type or "")
    if image_type is None:
        raise HTTPException(status_code=400, detail="Choose a JPEG, PNG, or WebP image.")
    content = await file.read(MAX_IMAGE_BYTES + 1)
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Images must be smaller than 10 MB.")
    extension, valid_signature = image_type
    if not valid_signature(content):
        raise HTTPException(status_code=400, detail="The file content does not match its image type.")
    filename = f"{prefix}-{secrets.token_hex(20)}.{extension}"
    object_path = f"{folder}/{filename}"
    storage_key = settings.supabase_secret_key or settings.supabase_service_role_key
    if not settings.supabase_url or not storage_key:
        raise HTTPException(
            status_code=503,
            detail="Image storage credentials are missing. Set SUPABASE_URL and SUPABASE_SECRET_KEY in the backend environment, then restart the backend.",
        )

    bucket = quote(bucket_name, safe="")
    encoded_path = quote(object_path, safe="/")
    storage_url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{encoded_path}"
    api_key = storage_key.get_secret_value()
    headers = {
        "apikey": api_key,
        "Content-Type": file.content_type or "application/octet-stream",
        "Cache-Control": "max-age=3600",
        "x-upsert": "false",
    }
    # New Supabase secret keys are API keys, not JWTs, so they must not be
    # sent as a bearer token. Keep legacy service_role JWTs working as well.
    if not api_key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                storage_url,
                content=content,
                headers=headers,
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Could not reach Supabase image storage.") from exc
    if response.is_error:
        message = response.text[:240] or "Supabase rejected the upload."
        raise HTTPException(status_code=502, detail=f"Supabase image upload failed: {message}")

    return f"{settings.supabase_url.rstrip('/')}/storage/v1/object/public/{bucket}/{encoded_path}"


@router.post("/profile-image/", status_code=201)
async def upload_profile_image(
    file: UploadFile = File(...),
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str | None]:
    image_url = await _save_image(file, settings.supabase_profile_bucket, "profiles", f"user-{user.id}")
    user.profile_image = image_url
    db.commit()
    db.refresh(user)
    return {"status": "success", "profile_image": user.profile_image}


@router.delete("/profile-image/", status_code=200)
def remove_profile_image(
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str | None]:
    user.profile_image = None
    db.commit()
    return {"status": "success", "profile_image": None}


@router.post("/article-image/", status_code=201)
async def upload_article_image(
    file: UploadFile = File(...),
    _: CustomUser = Depends(get_verified_provider),
) -> dict[str, str]:
    image_url = await _save_image(file, settings.supabase_article_bucket, "articles", "article")
    return {"status": "success", "image_url": image_url}
