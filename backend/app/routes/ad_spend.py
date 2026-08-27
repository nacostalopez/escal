from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, insert
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Store, ad_spend as ad_spend_table
from app.schemas.ad_spend import AdSpendCreate

router = APIRouter(prefix="/stores/{store_id}/ad-spend", tags=["ad-spend"])


@router.post("", status_code=201)
def ingest_ad_spend(store_id: UUID, payload: list[AdSpendCreate], db: Session = Depends(get_db)):
    if not db.get(Store, store_id):
        raise HTTPException(status_code=404, detail="Store not found")
    if not payload:
        return {"inserted": 0}

    rows = [{"store_id": store_id, **item.model_dump()} for item in payload]
    db.execute(insert(ad_spend_table), rows)
    db.commit()
    return {"inserted": len(rows)}


@router.get("")
def list_ad_spend(
    store_id: UUID,
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    platform: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(ad_spend_table).where(ad_spend_table.c.store_id == store_id)
    if start:
        stmt = stmt.where(ad_spend_table.c.time >= start)
    if end:
        stmt = stmt.where(ad_spend_table.c.time <= end)
    if platform:
        stmt = stmt.where(ad_spend_table.c.platform == platform)
    stmt = stmt.order_by(ad_spend_table.c.time.desc()).limit(500)
    return db.execute(stmt).mappings().all()
