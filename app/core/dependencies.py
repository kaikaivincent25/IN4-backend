from collections.abc import Iterator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.models.expert import Expert, ExpertStatus
from app.db.models.user import CustomUser
from app.db.session import get_db


_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> CustomUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = decode_token(credentials.credentials, "access")
    user = db.get(CustomUser, user_id) if user_id is not None else None
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> CustomUser | None:
    if credentials is None:
        return None
    user_id = decode_token(credentials.credentials, "access")
    user = db.get(CustomUser, user_id) if user_id is not None else None
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_verified_provider(
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomUser:
    expert = db.query(Expert).filter(Expert.user_id == user.id).one_or_none()
    if (
        not user.is_provider
        or expert is None
        or expert.status != ExpertStatus.VERIFIED.value
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only verified experts can perform this action.",
        )
    return user


def get_staff_user(user: CustomUser = Depends(get_current_user)) -> CustomUser:
    if not user.is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff permissions are required.",
        )
    return user
