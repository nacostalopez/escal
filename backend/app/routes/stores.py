from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import get_db
from app.models import Store, StoreCredential
from app.schemas.stores import StoreCreate, StoreOut, StoreCredentialCreate, StoreCredentialOut

router = APIRouter(prefix="/stores", tags=["stores"])


@router.post("", response_model=StoreOut, status_code=201)
def create_store(payload: StoreCreate, db: Session = Depends(get_db)):
    store = Store(**payload.model_dump())
    db.add(store)
    db.commit()
    db.refresh(store)
    return store


@router.get("", response_model=list[StoreOut])
def list_stores(account_id: UUID | None = None, db: Session = Depends(get_db)):
    query = db.query(Store)
    if account_id:
        query = query.filter(Store.account_id == account_id)
    return query.order_by(Store.created_at.desc()).all()


@router.get("/{store_id}", response_model=StoreOut)
def get_store(store_id: UUID, db: Session = Depends(get_db)):
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.put("/{store_id}/credentials", response_model=StoreCredentialOut)
def upsert_credentials(store_id: UUID, payload: StoreCredentialCreate, db: Session = Depends(get_db)):
    if not db.get(Store, store_id):
        raise HTTPException(status_code=404, detail="Store not found")

    stmt = (
        pg_insert(StoreCredential.__table__)
        .values(store_id=store_id, **payload.model_dump())
        .on_conflict_do_update(
            index_elements=["store_id", "provider"],
            set_=payload.model_dump(),
        )
        .returning(StoreCredential.__table__.c.id)
    )
    result = db.execute(stmt)
    db.commit()
    row_id = result.scalar_one()
    return db.get(StoreCredential, row_id)
