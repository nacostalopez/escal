-- Who fetched customer-linked data, and when. The only customer-linked
-- value exposed by any route today is the opaque customer_id UUID via
-- GET /stores/{id}/orders (Customer itself is hash-only, never returned
-- directly) — see app/routes/orders.py::list_orders.
CREATE TABLE customer_data_access_log (
    id UUID PRIMARY KEY,
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint VARCHAR(100) NOT NULL,
    accessed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_customer_data_access_log_store_time ON customer_data_access_log (store_id, accessed_at DESC);
