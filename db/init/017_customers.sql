-- Customer identity, hash-only (no plaintext/reversible PII at rest) — see
-- app/services/customers.py for the normalization+hashing recipe. Hashed
-- the same way Meta/Google Conversions APIs expect, so this table is
-- already CAPI-ready if that gets built later, without ever storing email
-- or phone in the clear.
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    email_hash VARCHAR(64),
    phone_hash VARCHAR(64),
    -- Shopify/Tiendanube's own customer id, kept for reference only.
    external_customer_id VARCHAR(255),
    first_order_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_customers_store_email ON customers(store_id, email_hash) WHERE email_hash IS NOT NULL;
CREATE INDEX idx_customers_store ON customers(store_id);

-- Nullable: an order with neither email nor phone (rare, but possible from
-- a minimal API-ingested row) simply has no linked customer. No FK
-- constraint, same as orders.store_id above it — enforced at the
-- application level (app/services/customers.py) like every other
-- hypertable-to-relational-table reference in this schema.
ALTER TABLE orders ADD COLUMN customer_id UUID;
