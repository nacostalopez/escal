from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.metrics import MetricsSummaryOut, DailyMetricOut

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
        ROUND((o.revenue / NULLIF(a.total_ad_spend, 0))::numeric, 2) AS true_roas
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


@router.get("/summary", response_model=MetricsSummaryOut)
def metrics_summary(
    store_id: UUID,
    start: datetime = Query(...),
    end: datetime = Query(...),
    db: Session = Depends(get_db),
):
    row = db.execute(SUMMARY_SQL, {"store_id": str(store_id), "start": start, "end": end}).mappings().one()
    return row


@router.get("/daily", response_model=list[DailyMetricOut])
def metrics_daily(
    store_id: UUID,
    start: datetime = Query(...),
    end: datetime = Query(...),
    db: Session = Depends(get_db),
):
    rows = db.execute(DAILY_SQL, {"store_id": str(store_id), "start": start, "end": end}).mappings().all()
    return rows
