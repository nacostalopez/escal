from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_owned_store, require_role
from app.models import Store, User
from app.models import orders as orders_table
from app.schemas.orders import OrderCreate, OrderOut
from app.services.customers import resolve_customer_id

router = APIRouter(prefix="/stores/{store_id}/orders", tags=["orders"])


@router.post("", status_code=201)
def ingest_orders(
    payload: list[OrderCreate],
    store: Store = Depends(get_owned_store),
    _: User = Depends(require_role("owner", "admin")),
    db: Session = Depends(get_db),
):
    if not payload:
        return {"inserted": 0}

    rows = []
    for item in payload:
        data = item.model_dump()
        email = data.pop("customer_email")
        phone = data.pop("customer_phone")
        data["customer_id"] = resolve_customer_id(db, store.id, email, phone)
        rows.append({"store_id": store.id, **data})

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
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    store: Store = Depends(get_owned_store),
    db: Session = Depends(get_db),
):
    stmt = select(orders_table).where(orders_table.c.store_id == store.id)
    if start:
        stmt = stmt.where(orders_table.c.time >= start)
    if end:
        stmt = stmt.where(orders_table.c.time <= end)
    stmt = stmt.order_by(orders_table.c.time.desc()).limit(500)
    return db.execute(stmt).mappings().all()
