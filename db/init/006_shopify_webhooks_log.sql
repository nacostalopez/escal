-- Audit log of received Shopify webhooks: signature validity + processing outcome
CREATE TABLE shopify_webhooks_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID REFERENCES stores(id) ON DELETE CASCADE,
    topic VARCHAR(100) NOT NULL,
    signature_valid BOOLEAN NOT NULL,
    status VARCHAR(20) NOT NULL, -- 'processed', 'rejected', 'error'
    error_message TEXT,
    received_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_shopify_webhooks_log_store_time ON shopify_webhooks_log (store_id, received_at DESC);
