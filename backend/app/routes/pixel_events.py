from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, insert
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Store, pixel_events as pixel_events_table
from app.schemas.pixel_events import PixelEventCreate

router = APIRouter(prefix="/stores/{store_id}/pixel-events", tags=["pixel-events"])


@router.post("", status_code=201)
def ingest_pixel_events(store_id: UUID, payload: list[PixelEventCreate], db: Session = Depends(get_db)):
    if not db.get(Store, store_id):
        raise HTTPException(status_code=404, detail="Store not found")
    if not payload:
        return {"inserted": 0}

    rows = [{"store_id": store_id, **item.model_dump()} for item in payload]
    db.execute(insert(pixel_events_table), rows)
    db.commit()
    return {"inserted": len(rows)}


@router.get("")
def list_pixel_events(
    store_id: UUID,
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    event_name: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(pixel_events_table).where(pixel_events_table.c.store_id == store_id)
    if start:
        stmt = stmt.where(pixel_events_table.c.time >= start)
    if end:
        stmt = stmt.where(pixel_events_table.c.time <= end)
    if event_name:
        stmt = stmt.where(pixel_events_table.c.event_name == event_name)
    stmt = stmt.order_by(pixel_events_table.c.time.desc()).limit(500)
    return db.execute(stmt).mappings().all()
