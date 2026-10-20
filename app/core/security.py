import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, encoded_password: str) -> bool:
    if encoded_password.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, digest = encoded_password.split("$", 3)
            actual = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode(),
                salt.encode(),
                int(iterations),
            )
            expected = base64.b64decode(digest, validate=True)
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False

    try:
        return password_context.verify(password, encoded_password)
    except (ValueError, TypeError):
        return False


def needs_password_rehash(encoded_password: str) -> bool:
    return encoded_password.startswith("pbkdf2_sha256$") or password_context.needs_update(
        encoded_password
    )


def _signing_key() -> str:
    if settings.jwt_secret_key is None:
        raise RuntimeError("JWT_SECRET_KEY must be configured before using authentication.")
    key = settings.jwt_secret_key.get_secret_value()
    if len(key) < 32:
        raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters.")
    return key


def create_token(user_id: int, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_days)
    )
    return jwt.encode(
        {
            "user_id": user_id,
            "token_type": token_type,
            "iat": now,
            "exp": expires_at,
        },
        _signing_key(),
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str, expected_type: str) -> int | None:
    try:
        payload = jwt.decode(
            token,
            _signing_key(),
            algorithms=[settings.jwt_algorithm],
        )
    except (JWTError, RuntimeError):
        return None
    user_id = payload.get("user_id")
    if payload.get("token_type") != expected_type or not isinstance(user_id, int):
        return None
    return user_id
