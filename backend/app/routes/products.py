from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import get_db
from app.models import Store, Product
from app.schemas.products import ProductUpsert, ProductOut

router = APIRouter(prefix="/stores/{store_id}/products", tags=["products"])


@router.put("", response_model=list[ProductOut])
def upsert_products(store_id: UUID, payload: list[ProductUpsert], db: Session = Depends(get_db)):
    if not db.get(Store, store_id):
        raise HTTPException(status_code=404, detail="Store not found")
    if not payload:
        return []

    rows = [{"store_id": store_id, **item.model_dump()} for item in payload]
    stmt = pg_insert(Product.__table__).values(rows)
    update_cols = {c: stmt.excluded[c] for c in ("sku", "title", "cogs", "shipping_cost")}
    stmt = stmt.on_conflict_do_update(
        index_elements=["store_id", "external_id"],
        set_=update_cols,
    ).returning(Product.__table__.c.id)
    result = db.execute(stmt)
    db.commit()
    ids = [r.id for r in result]
    return db.query(Product).filter(Product.id.in_(ids)).all()


@router.get("", response_model=list[ProductOut])
def list_products(store_id: UUID, db: Session = Depends(get_db)):
    return db.query(Product).filter(Product.store_id == store_id).all()
