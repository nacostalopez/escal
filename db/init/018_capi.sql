-- CAPI feedback loop (Meta Conversions API / Google Enhanced Conversions).
-- Opt-in per store+provider; capi_destination_id is the Meta pixel id or
-- Google conversionAction resource name, depending on `provider`. See
-- backend/app/services/capi.py.
ALTER TABLE store_credentials ADD COLUMN capi_enabled BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE store_credentials ADD COLUMN capi_destination_id VARCHAR(255);

-- One row per (store_id, order_id, provider) send attempt — doubles as the
-- idempotency check (never re-send an order already marked "sent") and the
-- audit trail (why a send failed).
CREATE TABLE capi_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    order_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    error TEXT,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX uq_capi_events_store_order_provider ON capi_events(store_id, order_id, provider);
