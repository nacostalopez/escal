-- Current sync status per store/provider, upserted after every OAuth connect or sync attempt.
-- Backs GET /stores/{id}/connectors/health.
CREATE TABLE connector_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID REFERENCES stores(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    last_synced_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_error TEXT,
    UNIQUE(store_id, provider)
);
