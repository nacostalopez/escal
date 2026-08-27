from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import get_db
from app.models import Store, orders as orders_table
from app.schemas.orders import OrderCreate, OrderOut

router = APIRouter(prefix="/stores/{store_id}/orders", tags=["orders"])


@router.post("", status_code=201)
def ingest_orders(store_id: UUID, payload: list[OrderCreate], db: Session = Depends(get_db)):
    if not db.get(Store, store_id):
        raise HTTPException(status_code=404, detail="Store not found")
    if not payload:
        return {"inserted": 0}

    rows = [{"store_id": store_id, **item.model_dump()} for item in payload]
    stmt = pg_insert(orders_table).values(rows)
    update_cols = {
        c.name: stmt.excluded[c.name]
        for c in orders_table.c
        if c.name not in ("time", "store_id", "order_id", "net_profit")
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=["store_id", "order_id", "time"],
        set_=update_cols,
    )
    db.execute(stmt)
    db.commit()
    return {"inserted": len(rows)}


@router.get("", response_model=list[OrderOut])
def list_orders(
    store_id: UUID,
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(orders_table).where(orders_table.c.store_id == store_id)
    if start:
        stmt = stmt.where(orders_table.c.time >= start)
    if end:
        stmt = stmt.where(orders_table.c.time <= end)
    stmt = stmt.order_by(orders_table.c.time.desc()).limit(500)
    return db.execute(stmt).mappings().all()
