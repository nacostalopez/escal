-- Every Tiendanube webhook received, valid or not (mirrors shopify_webhooks_log).
CREATE TABLE tiendanube_webhooks_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID REFERENCES stores(id) ON DELETE CASCADE,
    topic VARCHAR(100) NOT NULL,
    signature_valid BOOLEAN NOT NULL,
    status VARCHAR(20) NOT NULL,  -- 'processed', 'rejected', 'error'
    error_message TEXT,
    received_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tiendanube_webhooks_log_store_time ON tiendanube_webhooks_log(store_id, received_at DESC);

-- Provider-side account/store identifier captured at OAuth time (Tiendanube's
-- own store id, MercadoPago's collector id) so later API calls don't require
-- the caller to keep re-supplying it. Nullable — Shopify/Meta/Google don't use it.
ALTER TABLE store_credentials ADD COLUMN provider_account_id VARCHAR(255);
