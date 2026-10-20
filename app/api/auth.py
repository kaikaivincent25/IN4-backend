from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import (
    create_token,
    hash_password,
    needs_password_rehash,
    verify_password,
    decode_token,
)
from app.db.models.user import CustomUser
from app.db.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    ProfileResponse,
    ProfileUpdateRequest,
    RegisterRequest,
    TokenPair,
    TokenRefreshRequest,
    TokenRefreshResponse,
)
from app.db.schemas.users import UserPublic, UserRead
from app.db.session import get_db


router = APIRouter(prefix="/api/auth", tags=["authentication"])


def _tokens_for(user: CustomUser) -> TokenPair:
    return TokenPair(
        access=create_token(user.id, "access"),
        refresh=create_token(user.id, "refresh"),
    )


def _auth_response(user: CustomUser, message: str) -> AuthResponse:
    return AuthResponse(
        status="success",
        message=message,
        user=UserPublic.model_validate(user),
        tokens=_tokens_for(user),
    )


@router.post("/register/", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    existing_user = db.scalar(
        select(CustomUser).where(func.lower(CustomUser.email) == payload.email)
    )
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    user = CustomUser(
        email=payload.email,
        password=hash_password(payload.password),
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        is_consumer=True,
        is_provider=False,
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        ) from exc
    db.refresh(user)
    return _auth_response(user, "Registration successful.")


@router.post("/login/", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(
        select(CustomUser).where(func.lower(CustomUser.email) == payload.email)
    )
    if user is None or not verify_password(payload.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account is inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if needs_password_rehash(user.password):
        user.password = hash_password(payload.password)
        db.commit()
        db.refresh(user)
    return _auth_response(user, "Login successful.")


@router.post("/token/refresh/", response_model=TokenRefreshResponse)
def refresh_token(
    payload: TokenRefreshRequest,
    db: Session = Depends(get_db),
) -> TokenRefreshResponse:
    user_id = decode_token(payload.refresh, "refresh")
    user = db.get(CustomUser, user_id) if user_id is not None else None
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenRefreshResponse(access=create_token(user.id, "access"))


@router.get("/profile/", response_model=ProfileResponse)
def get_profile(user: CustomUser = Depends(get_current_user)) -> ProfileResponse:
    return ProfileResponse(user=UserRead.model_validate(user))


@router.put("/profile/", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    for field in ("first_name", "last_name"):
        if field in payload.model_fields_set:
            value = getattr(payload, field)
            setattr(user, field, value.strip() if value is not None else None)
    db.commit()
    db.refresh(user)
    return ProfileResponse(
        message="Profile updated successfully.",
        user=UserRead.model_validate(user),
    )


@router.post("/change-password/", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    if not verify_password(payload.old_password, user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    user.password = hash_password(payload.new_password)
    db.commit()
    return MessageResponse(message="Password changed successfully.")


@router.post("/logout/", response_model=MessageResponse)
def logout(_: CustomUser = Depends(get_current_user)) -> MessageResponse:
    return MessageResponse(message="Logged out successfully.")
