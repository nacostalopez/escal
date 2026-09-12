from sqlalchemy import Column, DateTime, Integer, MetaData, Numeric, String, Table
from sqlalchemy.dialects.postgresql import UUID

metadata = MetaData()

orders = Table(
    "orders",
    metadata,
    Column("time", DateTime(timezone=True), nullable=False),
    Column("store_id", UUID(as_uuid=True), nullable=False),
    Column("order_id", String(255), nullable=False),
    Column("gross_amount", Numeric(12, 4), nullable=False),
    Column("discounts", Numeric(12, 4)),
    Column("shipping_fee", Numeric(12, 4)),
    Column("payment_gateway_fee", Numeric(12, 4)),
    Column("cogs_total", Numeric(12, 4)),
    Column("net_profit", Numeric(12, 4)),  # generated column, read-only
    Column("currency", String(3), nullable=False),
    Column("attribution_utm_source", String(100)),
    Column("attribution_utm_campaign", String(100)),
    Column("utm_medium", String(100)),
    Column("utm_content", String(100)),
    Column("click_id", String(255)),
    Column("landing_url", String(2048)),
    # Nullable — an order with neither email nor phone has no linked
    # customer. See app/services/customers.py::resolve_customer_id. No FK
    # constraint, same as store_id above — Customer is ORM-managed and gets
    # created/dropped fresh every pytest session, while orders (a hypertable
    # Core Table, never touched by Base.metadata.create_all/drop_all)
    # persists across test runs; a real FK would make test teardown fail
    # (Postgres refuses to drop customers while orders still references it).
    Column("customer_id", UUID(as_uuid=True)),
)

pixel_events = Table(
    "pixel_events",
    metadata,
    Column("time", DateTime(timezone=True), nullable=False),
    Column("store_id", UUID(as_uuid=True), nullable=False),
    Column("event_name", String(50), nullable=False),
    Column("event_id", String(255)),
    Column("anonymous_id", String(255)),
    Column("user_email_hash", String(64)),
    Column("utm_source", String(100)),
    Column("utm_medium", String(100)),
    Column("utm_campaign", String(100)),
    Column("utm_content", String(100)),
)

ad_spend = Table(
    "ad_spend",
    metadata,
    Column("time", DateTime(timezone=True), nullable=False),
    Column("store_id", UUID(as_uuid=True), nullable=False),
    Column("platform", String(50), nullable=False),
    Column("campaign_id", String(255), nullable=False),
    Column("campaign_name", String(255)),
    Column("adset_id", String(255)),
    Column("spend", Numeric(12, 4), nullable=False),
    Column("impressions", Integer),
    Column("clicks", Integer),
)

creative_performance = Table(
    "creative_performance",
    metadata,
    Column("time", DateTime(timezone=True), nullable=False),
    Column("store_id", UUID(as_uuid=True), nullable=False),
    Column("platform", String(50), nullable=False),
    Column("campaign_id", String(255), nullable=False),
    Column("campaign_name", String(255)),
    Column("adset_id", String(255)),
    Column("ad_id", String(255), nullable=False),
    Column("ad_name", String(255)),
    Column("thumbnail_url", String(500)),
    Column("spend", Numeric(12, 4), nullable=False),
    Column("impressions", Integer),
    Column("clicks", Integer),
)
