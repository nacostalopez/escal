from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class OrderCreate(BaseModel):
    time: datetime
    order_id: str
    gross_amount: float
    discounts: float = 0.0
    shipping_fee: float = 0.0
    payment_gateway_fee: float = 0.0
    cogs_total: float = 0.0
    currency: str
    attribution_utm_source: str | None = None
    attribution_utm_campaign: str | None = None


class OrderOut(OrderCreate):
    store_id: UUID
    net_profit: float | None = None
