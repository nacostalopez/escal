from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import get_db
from app.dependencies import get_current_user, get_owned_store
from app.models import Store, StoreCredential, User
from app.schemas.stores import StoreCreate, StoreOut, StoreCredentialCreate, StoreCredentialOut
from app.security import encrypt_secret

router = APIRouter(prefix="/stores", tags=["stores"])


@router.post("", response_model=StoreOut, status_code=201)
def create_store(payload: StoreCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = Store(account_id=current_user.account_id, **payload.model_dump())
    db.add(store)
    db.commit()
    db.refresh(store)
    return store


@router.get("", response_model=list[StoreOut])
def list_stores(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Store)
        .filter(Store.account_id == current_user.account_id)
        .order_by(Store.created_at.desc())
        .all()
    )


@router.get("/{store_id}", response_model=StoreOut)
def get_store(store: Store = Depends(get_owned_store)):
    return store


@router.put("/{store_id}/credentials", response_model=StoreCredentialOut)
def upsert_credentials(
    payload: StoreCredentialCreate,
    store: Store = Depends(get_owned_store),
    db: Session = Depends(get_db),
):
    data = payload.model_dump()
    data["access_token"] = encrypt_secret(data["access_token"])
    if data.get("refresh_token"):
        data["refresh_token"] = encrypt_secret(data["refresh_token"])

    stmt = (
        pg_insert(StoreCredential.__table__)
        .values(store_id=store.id, **data)
        .on_conflict_do_update(
            index_elements=["store_id", "provider"],
            set_=data,
        )
        .returning(StoreCredential.__table__.c.id)
    )
    result = db.execute(stmt)
    db.commit()
    row_id = result.scalar_one()
    return db.get(StoreCredential, row_id)
