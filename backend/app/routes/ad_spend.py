from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_owned_store, require_store_role
from app.models import Store, User
from app.models import ad_spend as ad_spend_table
from app.schemas.ad_spend import AdSpendCreate

router = APIRouter(prefix="/stores/{store_id}/ad-spend", tags=["ad-spend"])


@router.post("", status_code=201)
def ingest_ad_spend(
    payload: list[AdSpendCreate],
    store: Store = Depends(get_owned_store),
    _: User = Depends(require_store_role("owner", "admin")),
    db: Session = Depends(get_db),
):
    if not payload:
        return {"inserted": 0}

    rows = [{"store_id": store.id, **item.model_dump()} for item in payload]
    db.execute(insert(ad_spend_table), rows)
    db.commit()
    return {"inserted": len(rows)}


@router.get("")
def list_ad_spend(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    platform: str | None = Query(default=None),
    store: Store = Depends(get_owned_store),
    db: Session = Depends(get_db),
):
    stmt = select(ad_spend_table).where(ad_spend_table.c.store_id == store.id)
    if start:
        stmt = stmt.where(ad_spend_table.c.time >= start)
    if end:
        stmt = stmt.where(ad_spend_table.c.time <= end)
    if platform:
        stmt = stmt.where(ad_spend_table.c.platform == platform)
    stmt = stmt.order_by(ad_spend_table.c.time.desc()).limit(500)
    return db.execute(stmt).mappings().all()
