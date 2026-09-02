from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Account, RefreshToken, User
from app.rate_limit import limiter
from app.schemas.auth import LoginIn, LogoutIn, RefreshIn, RegisterIn, TokenOut, UserOut
from app.security import create_access_token, create_refresh_token, hash_password, hash_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def issue_tokens(db: Session, user: User) -> TokenOut:
    """Create an access/refresh token pair for user, persisting the refresh
    token's hash. Shared by register, login, and accept_invite."""
    raw_refresh_token = create_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    ))
    db.commit()

    return TokenOut(
        access_token=create_access_token(user.id, user.account_id),
        refresh_token=raw_refresh_token,
    )


@router.post("/register", response_model=TokenOut, status_code=201)
@limiter.limit("5/minute")
def register(request: Request, payload: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    account = Account(name=payload.account_name)
    db.add(account)
    db.flush()

    user = User(
        account_id=account.id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role="owner",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return issue_tokens(db, user)


@router.post("/login", response_model=TokenOut)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    return issue_tokens(db, user)


@router.post("/refresh", response_model=TokenOut)
@limiter.limit("10/minute")
def refresh(request: Request, payload: RefreshIn, db: Session = Depends(get_db)):
    """Rotate a refresh token: the presented token is revoked and a new
    access/refresh pair is issued. Reusing an already-rotated (or expired,
    or never-issued) token is rejected outright."""
    token_row = db.query(RefreshToken).filter_by(token_hash=hash_token(payload.refresh_token)).first()

    now = datetime.now(timezone.utc)
    if not token_row or token_row.revoked_at is not None or token_row.expires_at < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user = db.get(User, token_row.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    token_row.revoked_at = now
    db.commit()

    return issue_tokens(db, user)


@router.post("/logout", status_code=204)
def logout(payload: LogoutIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Revoke a single refresh token (this device/session only)."""
    token_row = db.query(RefreshToken).filter_by(token_hash=hash_token(payload.refresh_token)).first()
    if not token_row or token_row.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refresh token not found")

    token_row.revoked_at = datetime.now(timezone.utc)
    db.commit()


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
