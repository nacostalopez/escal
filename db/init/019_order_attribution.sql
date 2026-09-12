-- Orders previously only captured utm_source/utm_campaign; both webhook
-- connectors already receive more attribution data than they stored. This
-- closes that gap so ad-level ROAS and channel-level CAC (planned next) have
-- something to join against.
ALTER TABLE orders
    ADD COLUMN utm_medium VARCHAR(100),
    ADD COLUMN utm_content VARCHAR(100),
    -- Normalized click identifier, "fb:<fbclid>" or "g:<gclid>" — see
    -- app/connectors/attribution.py::extract_click_id.
    ADD COLUMN click_id VARCHAR(255),
    ADD COLUMN landing_url VARCHAR(2048);
