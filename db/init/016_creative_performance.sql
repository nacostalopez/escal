-- Ad-level (creative) performance — separate from ad_spend (campaign/adset
-- level) because cardinality is much higher here (one row per ad per day,
-- not per campaign) and it carries extra identity columns ad_spend doesn't
-- need. Meta/Google only for now — Tiendanube/MercadoPago aren't
-- creative-based ad platforms.
CREATE TABLE creative_performance (
    time TIMESTAMPTZ NOT NULL,
    store_id UUID NOT NULL,
    platform VARCHAR(50) NOT NULL,
    campaign_id VARCHAR(255) NOT NULL,
    campaign_name VARCHAR(255),
    adset_id VARCHAR(255),
    ad_id VARCHAR(255) NOT NULL,
    ad_name VARCHAR(255),
    -- Populated once a connector fetches it (not yet implemented for either
    -- platform — needs a separate per-creative API call on both sides).
    thumbnail_url VARCHAR(500),
    spend NUMERIC(12, 4) NOT NULL,
    impressions INT DEFAULT 0,
    clicks INT DEFAULT 0
);

SELECT create_hypertable('creative_performance', 'time');

CREATE INDEX idx_creative_performance_store_time ON creative_performance (store_id, time DESC);
