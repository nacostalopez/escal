from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_owned_store, require_store_role
from app.models import Store, User
from app.models import creative_performance as creative_performance_table
from app.schemas.creative_performance import CreativePerformanceCreate

router = APIRouter(prefix="/stores/{store_id}/creative-performance", tags=["creative-performance"])


@router.post("", status_code=201)
def ingest_creative_performance(
    payload: list[CreativePerformanceCreate],
    store: Store = Depends(get_owned_store),
    _: User = Depends(require_store_role("owner", "admin")),
    db: Session = Depends(get_db),
):
    if not payload:
        return {"inserted": 0}

    rows = [{"store_id": store.id, **item.model_dump()} for item in payload]
    db.execute(insert(creative_performance_table), rows)
    db.commit()
    return {"inserted": len(rows)}


@router.get("")
def list_creative_performance(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    platform: str | None = Query(default=None),
    store: Store = Depends(get_owned_store),
    db: Session = Depends(get_db),
):
    stmt = select(creative_performance_table).where(creative_performance_table.c.store_id == store.id)
    if start:
        stmt = stmt.where(creative_performance_table.c.time >= start)
    if end:
        stmt = stmt.where(creative_performance_table.c.time <= end)
    if platform:
        stmt = stmt.where(creative_performance_table.c.platform == platform)
    stmt = stmt.order_by(creative_performance_table.c.time.desc()).limit(500)
    return db.execute(stmt).mappings().all()
