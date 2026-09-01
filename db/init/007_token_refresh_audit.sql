-- Audit log of OAuth token refresh attempts across connectors (currently: Google Ads)
CREATE TABLE token_refresh_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID REFERENCES stores(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    refreshed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_token_refresh_audit_store_time ON token_refresh_audit (store_id, refreshed_at DESC);
