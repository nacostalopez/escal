CREATE MATERIALIZED VIEW daily_financial_summary
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS day,
    store_id,
    COUNT(DISTINCT order_id) AS total_orders,
    SUM(gross_amount) AS total_revenue,
    SUM(cogs_total) AS total_cogs,
    SUM(payment_gateway_fee) AS total_gateway_fees,
    SUM(net_profit) AS total_net_profit
FROM orders
GROUP BY day, store_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('daily_financial_summary',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

-- Refresh immediately so the view isn't empty on a fresh dev DB
CALL refresh_continuous_aggregate('daily_financial_summary', NULL, NULL);
