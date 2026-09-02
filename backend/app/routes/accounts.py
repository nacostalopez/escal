import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import AccountInvite, User
from app.schemas.accounts import (
    AccountOut,
    InviteAcceptIn,
    InviteCreate,
    InviteOut,
    MemberOut,
    RoleUpdateIn,
)
from app.schemas.auth import TokenOut
from app.security import create_access_token, hash_password

router = APIRouter(prefix="/accounts", tags=["accounts"])

INVITE_EXPIRY_DAYS = 7


@router.get("/me", response_model=AccountOut)
def get_my_account(current_user: User = Depends(get_current_user)):
    return current_user.account


@router.get("/members", response_model=list[MemberOut])
def list_members(
    current_user: User = Depends(require_role("owner", "admin")),
    db: Session = Depends(get_db),
):
    return (
        db.query(User)
        .filter(User.account_id == current_user.account_id)
        .order_by(User.created_at.asc())
        .all()
    )


@router.post("/invites", response_model=InviteOut, status_code=201)
def create_invite(
    payload: InviteCreate,
    current_user: User = Depends(require_role("owner")),
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    existing_pending = db.query(AccountInvite).filter_by(
        account_id=current_user.account_id,
        email=payload.email,
        status="pending",
    ).first()
    if existing_pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An invite to this email is already pending")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    invite = AccountInvite(
        id=uuid4(),
        account_id=current_user.account_id,
        email=payload.email,
        role=payload.role,
        invited_by=current_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITE_EXPIRY_DAYS),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    result = InviteOut.model_validate(invite)
    result.token = raw_token
    return result


@router.get("/invites", response_model=list[InviteOut])
def list_invites(
    current_user: User = Depends(require_role("owner")),
    db: Session = Depends(get_db),
):
    return (
        db.query(AccountInvite)
        .filter(AccountInvite.account_id == current_user.account_id, AccountInvite.status == "pending")
        .order_by(AccountInvite.created_at.desc())
        .all()
    )


@router.delete("/invites/{invite_id}", status_code=204)
def revoke_invite(
    invite_id: UUID,
    current_user: User = Depends(require_role("owner")),
    db: Session = Depends(get_db),
):
    invite = db.get(AccountInvite, invite_id)
    if not invite or invite.account_id != current_user.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")

    invite.status = "revoked"
    db.commit()


@router.post("/invites/accept", response_model=TokenOut)
def accept_invite(payload: InviteAcceptIn, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    invite = db.query(AccountInvite).filter_by(token_hash=token_hash).first()

    now = datetime.now(timezone.utc)
    if not invite or invite.status != "pending" or invite.expires_at < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired invite")

    if db.query(User).filter(User.email == invite.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        id=uuid4(),
        account_id=invite.account_id,
        email=invite.email,
        hashed_password=hash_password(payload.password),
        role=invite.role,
    )
    db.add(user)

    invite.status = "accepted"
    invite.accepted_at = now

    db.commit()
    db.refresh(user)

    return TokenOut(access_token=create_access_token(user.id, user.account_id))


@router.patch("/members/{user_id}/role", response_model=MemberOut)
def update_member_role(
    user_id: UUID,
    payload: RoleUpdateIn,
    current_user: User = Depends(require_role("owner")),
    db: Session = Depends(get_db),
):
    member = db.get(User, user_id)
    if not member or member.account_id != current_user.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if member.role == "owner" and payload.role != "owner":
        remaining_owners = db.query(User).filter(
            User.account_id == current_user.account_id, User.role == "owner", User.id != member.id,
        ).count()
        if remaining_owners == 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot demote the last owner")

    member.role = payload.role
    db.commit()
    db.refresh(member)
    return member


@router.delete("/members/{user_id}", status_code=204)
def remove_member(
    user_id: UUID,
    current_user: User = Depends(require_role("owner")),
    db: Session = Depends(get_db),
):
    member = db.get(User, user_id)
    if not member or member.account_id != current_user.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if member.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove yourself")

    if member.role == "owner":
        remaining_owners = db.query(User).filter(
            User.account_id == current_user.account_id, User.role == "owner", User.id != member.id,
        ).count()
        if remaining_owners == 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot remove the last owner")

    db.delete(member)
    db.commit()
