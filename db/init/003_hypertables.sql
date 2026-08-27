-- A. Ventas y Financiero
CREATE TABLE orders (
    time TIMESTAMPTZ NOT NULL,
    store_id UUID NOT NULL,
    order_id VARCHAR(255) NOT NULL,
    gross_amount NUMERIC(12, 4) NOT NULL,
    discounts NUMERIC(12, 4) DEFAULT 0.0,
    shipping_fee NUMERIC(12, 4) DEFAULT 0.0,
    payment_gateway_fee NUMERIC(12, 4) DEFAULT 0.0,
    cogs_total NUMERIC(12, 4) DEFAULT 0.0,
    net_profit NUMERIC(12, 4) GENERATED ALWAYS AS (
        gross_amount - discounts - shipping_fee - payment_gateway_fee - cogs_total
    ) STORED,
    currency VARCHAR(3) NOT NULL,
    attribution_utm_source VARCHAR(100),
    attribution_utm_campaign VARCHAR(100)
);

SELECT create_hypertable('orders', 'time');

CREATE INDEX idx_orders_store_time ON orders (store_id, time DESC);
-- Uniqueness must include the partitioning column on a hypertable
CREATE UNIQUE INDEX idx_orders_store_order_time ON orders (store_id, order_id, time);

-- B. Eventos del Pixel / CAPI
CREATE TABLE pixel_events (
    time TIMESTAMPTZ NOT NULL,
    store_id UUID NOT NULL,
    event_name VARCHAR(50) NOT NULL,
    event_id VARCHAR(255),
    anonymous_id VARCHAR(255),
    user_email_hash VARCHAR(64),
    utm_source VARCHAR(100),
    utm_medium VARCHAR(100),
    utm_campaign VARCHAR(100),
    utm_content VARCHAR(100)
);

SELECT create_hypertable('pixel_events', 'time');

CREATE INDEX idx_pixel_events_store_time ON pixel_events (store_id, time DESC);

-- C. Gasto Publicitario Diario
CREATE TABLE ad_spend (
    time TIMESTAMPTZ NOT NULL,
    store_id UUID NOT NULL,
    platform VARCHAR(50) NOT NULL,
    campaign_id VARCHAR(255) NOT NULL,
    campaign_name VARCHAR(255),
    adset_id VARCHAR(255),
    spend NUMERIC(12, 4) NOT NULL,
    impressions INT DEFAULT 0,
    clicks INT DEFAULT 0
);

SELECT create_hypertable('ad_spend', 'time');

CREATE INDEX idx_ad_spend_store_time ON ad_spend (store_id, time DESC);
