import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt
from cryptography.fernet import Fernet
from fastapi import HTTPException, status

from app.config import settings

_fernet = Fernet(settings.credentials_encryption_key.encode())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed_password.encode())


def create_access_token(user_id: UUID, account_id: UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "account_id": str(account_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def hash_token(raw_token: str) -> str:
    """SHA-256 hex digest used to store opaque tokens (refresh tokens, invite
    tokens) at rest — the raw value is only ever returned once, in the
    response that creates it."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_refresh_token() -> str:
    """Generate a new opaque refresh token (raw value — caller persists its
    hash_token() result plus an expiry as a RefreshToken row)."""
    return secrets.token_urlsafe(32)


def create_oauth_state_token() -> str:
    """Generate a new opaque OAuth CSRF state token (raw value — caller
    persists its hash_token() result plus an expiry as an OAuthState row)."""
    return secrets.token_urlsafe(32)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def encrypt_secret(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return _fernet.decrypt(value.encode()).decode()
