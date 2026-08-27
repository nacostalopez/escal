from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProductUpsert(BaseModel):
    external_id: str
    sku: str | None = None
    title: str
    cogs: float = 0.0
    shipping_cost: float = 0.0


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    store_id: UUID
    external_id: str
    sku: str | None = None
    title: str
    cogs: float
    shipping_cost: float
