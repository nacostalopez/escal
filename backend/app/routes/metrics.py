from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_owned_store
from app.models import Store
from app.schemas.metrics import CreativeMetricOut, DailyMetricOut, MetricsSummaryOut

router = APIRouter(prefix="/stores/{store_id}/metrics", tags=["metrics"])

# Summary reads straight from the `orders` hypertable so it's accurate the
# instant an order is ingested (the continuous aggregate can lag up to an
# hour behind, see /daily below).
SUMMARY_SQL = text(
    """
    WITH metrics_orders AS (
        SELECT
            COALESCE(SUM(gross_amount), 0) AS revenue,
            COALESCE(SUM(net_profit), 0) AS net_profit
        FROM orders
        WHERE store_id = :store_id
          AND time BETWEEN :start AND :end
    ),
    metrics_ads AS (
        SELECT COALESCE(SUM(spend), 0) AS total_ad_spend
        FROM ad_spend
        WHERE store_id = :store_id
          AND time BETWEEN :start AND :end
    )
    SELECT
        o.revenue,
        o.net_profit,
        a.total_ad_spend,
        (o.net_profit - a.total_ad_spend) AS real_profit_after_ads,
        -- Unlike plain ROAS (revenue / spend), this is net of discounts,
        -- shipping, payment-gateway fees and COGS (net_profit is a
        -- GENERATED column on orders, see db/init/003_hypertables.sql) —
        -- it answers "how much profit per ad dollar", not "how much
        -- revenue per ad dollar".
        ROUND((o.net_profit / NULLIF(a.total_ad_spend, 0))::numeric, 2) AS true_roas
    FROM metrics_orders o, metrics_ads a
    """
)

# Daily breakdown reads from the daily_financial_summary continuous
# aggregate (fast, but refreshed on an hourly schedule) joined with daily
# ad spend.
DAILY_SQL = text(
    """
    WITH ads_by_day AS (
        SELECT time_bucket('1 day', time) AS day, SUM(spend) AS spend
        FROM ad_spend
        WHERE store_id = :store_id
          AND time BETWEEN :start AND :end
        GROUP BY day
    )
    SELECT
        f.day,
        f.total_orders,
        f.total_revenue,
        f.total_cogs,
        f.total_gateway_fees,
        f.total_net_profit,
        COALESCE(a.spend, 0) AS ad_spend
    FROM daily_financial_summary f
    LEFT JOIN ads_by_day a ON a.day = f.day
    WHERE f.store_id = :store_id
      AND f.day BETWEEN :start AND :end
    ORDER BY f.day
    """
)


# One row per ad (creative), summed across the range and ranked by spend —
# what a media buyer scans first to decide what to scale or kill. MAX() on
# the text columns is safe here since they're functionally dependent on
# ad_id (a given ad doesn't change name/campaign mid-range in practice).
CREATIVES_SQL = text(
    """
    SELECT
        platform,
        ad_id,
        MAX(ad_name) AS ad_name,
        MAX(campaign_name) AS campaign_name,
        MAX(thumbnail_url) AS thumbnail_url,
        SUM(spend) AS spend,
        SUM(impressions) AS impressions,
        SUM(clicks) AS clicks,
        ROUND((SUM(clicks)::numeric / NULLIF(SUM(impressions), 0)) * 100, 2) AS ctr,
        ROUND((SUM(spend) / NULLIF(SUM(clicks), 0))::numeric, 4) AS cpc,
        ROUND((SUM(spend) / NULLIF(SUM(impressions), 0) * 1000)::numeric, 4) AS cpm
    FROM creative_performance
    WHERE store_id = :store_id
      AND time BETWEEN :start AND :end
    GROUP BY platform, ad_id
    ORDER BY spend DESC
    """
)


@router.get("/summary", response_model=MetricsSummaryOut)
def metrics_summary(
    start: datetime = Query(...),
    end: datetime = Query(...),
    store: Store = Depends(get_owned_store),
    db: Session = Depends(get_db),
):
    row = db.execute(SUMMARY_SQL, {"store_id": str(store.id), "start": start, "end": end}).mappings().one()
    return row


@router.get("/daily", response_model=list[DailyMetricOut])
def metrics_daily(
    start: datetime = Query(...),
    end: datetime = Query(...),
    store: Store = Depends(get_owned_store),
    db: Session = Depends(get_db),
):
    rows = db.execute(DAILY_SQL, {"store_id": str(store.id), "start": start, "end": end}).mappings().all()
    return rows


@router.get("/creatives", response_model=list[CreativeMetricOut])
def metrics_creatives(
    start: datetime = Query(...),
    end: datetime = Query(...),
    store: Store = Depends(get_owned_store),
    db: Session = Depends(get_db),
):
    rows = db.execute(CREATIVES_SQL, {"store_id": str(store.id), "start": start, "end": end}).mappings().all()
    return rows
