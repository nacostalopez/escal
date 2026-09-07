-- CSRF state tokens for the OAuth handshake (Shopify/Meta/Google/Tiendanube/
-- MercadoPago). Issued by each */auth-url endpoint, burned by the matching
-- */callback endpoint — closes the gap where a callback was accepted with
-- no proof it followed this store's own auth-url step.
CREATE TABLE oauth_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ  -- NULL = still valid/unused
);

CREATE INDEX idx_oauth_states_store ON oauth_states(store_id);
