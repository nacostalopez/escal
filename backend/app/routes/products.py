from fastapi import APIRouter, Depends
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_owned_store
from app.models import Product, Store
from app.schemas.products import ProductOut, ProductUpsert

router = APIRouter(prefix="/stores/{store_id}/products", tags=["products"])


@router.put("", response_model=list[ProductOut])
def upsert_products(payload: list[ProductUpsert], store: Store = Depends(get_owned_store), db: Session = Depends(get_db)):
    if not payload:
        return []

    rows = [{"store_id": store.id, **item.model_dump()} for item in payload]
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
def list_products(store: Store = Depends(get_owned_store), db: Session = Depends(get_db)):
    return db.query(Product).filter(Product.store_id == store.id).all()
