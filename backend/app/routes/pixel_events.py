from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_owned_store
from app.models import Store
from app.models import pixel_events as pixel_events_table
from app.schemas.pixel_events import PixelEventCreate

router = APIRouter(prefix="/stores/{store_id}/pixel-events", tags=["pixel-events"])


@router.post("", status_code=201)
def ingest_pixel_events(
    payload: list[PixelEventCreate],
    store: Store = Depends(get_owned_store),
    db: Session = Depends(get_db),
):
    if not payload:
        return {"inserted": 0}

    rows = [{"store_id": store.id, **item.model_dump()} for item in payload]
    db.execute(insert(pixel_events_table), rows)
    db.commit()
    return {"inserted": len(rows)}


@router.get("")
def list_pixel_events(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    event_name: str | None = Query(default=None),
    store: Store = Depends(get_owned_store),
    db: Session = Depends(get_db),
):
    stmt = select(pixel_events_table).where(pixel_events_table.c.store_id == store.id)
    if start:
        stmt = stmt.where(pixel_events_table.c.time >= start)
    if end:
        stmt = stmt.where(pixel_events_table.c.time <= end)
    if event_name:
        stmt = stmt.where(pixel_events_table.c.event_name == event_name)
    stmt = stmt.order_by(pixel_events_table.c.time.desc()).limit(500)
    return db.execute(stmt).mappings().all()
