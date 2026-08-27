from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account
from app.schemas.accounts import AccountCreate, AccountOut

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountOut, status_code=201)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    account = Account(name=payload.name)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db)):
    return db.query(Account).order_by(Account.created_at.desc()).all()


@router.get("/{account_id}", response_model=AccountOut)
def get_account(account_id: UUID, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account
