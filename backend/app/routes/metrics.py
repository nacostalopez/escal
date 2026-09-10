from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_owned_store
from app.models import Store
from app.schemas.metrics import CohortLtvOut, CreativeMetricOut, DailyMetricOut, MetricsSummaryOut

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


# Unlike every other endpoint here, :start/:end filter *cohorts* (by
# first_order_at), not orders — the LTV curve for a cohort looks forward
# from its acquisition month regardless of :end, capped by :months. A
# cohort acquired last month can only ever have one populated month-offset;
# that's correct cohort-analysis behavior, not a bug. CAC is blended
# (total ad_spend in the cohort's acquisition month / new_customers) —
# no per-channel attribution yet.
LTV_COHORTS_SQL = text(
    """
    WITH cohorts AS (
        SELECT id, date_trunc('month', first_order_at) AS cohort_month
        FROM customers
        WHERE store_id = :store_id
          AND first_order_at BETWEEN :start AND :end
    ),
    cohort_sizes AS (
        SELECT cohort_month, COUNT(*) AS new_customers
        FROM cohorts
        GROUP BY cohort_month
    ),
    order_months AS (
        SELECT
            c.cohort_month,
            (
                (EXTRACT(YEAR FROM o.time) - EXTRACT(YEAR FROM c.cohort_month)) * 12
                + (EXTRACT(MONTH FROM o.time) - EXTRACT(MONTH FROM c.cohort_month))
            )::int AS month_offset,
            o.net_profit
        FROM orders o
        JOIN cohorts c ON o.customer_id = c.id
    ),
    monthly_profit AS (
        SELECT cohort_month, month_offset, SUM(net_profit) AS profit
        FROM order_months
        WHERE month_offset BETWEEN 0 AND :months - 1
        GROUP BY cohort_month, month_offset
    ),
    cumulative AS (
        SELECT
            cohort_month,
            month_offset,
            SUM(profit) OVER (PARTITION BY cohort_month ORDER BY month_offset) AS cumulative_profit
        FROM monthly_profit
    ),
    spend AS (
        SELECT date_trunc('month', time) AS cohort_month, SUM(spend) AS spend
        FROM ad_spend
        WHERE store_id = :store_id
        GROUP BY cohort_month
    )
    SELECT
        cs.cohort_month,
        cs.new_customers,
        sp.spend / NULLIF(cs.new_customers, 0) AS cac,
        cu.month_offset,
        cu.cumulative_profit / NULLIF(cs.new_customers, 0) AS avg_cumulative_ltv
    FROM cohort_sizes cs
    LEFT JOIN spend sp ON sp.cohort_month = cs.cohort_month
    LEFT JOIN cumulative cu ON cu.cohort_month = cs.cohort_month
    ORDER BY cs.cohort_month, cu.month_offset
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


@router.get("/ltv-cohorts", response_model=list[CohortLtvOut])
def metrics_ltv_cohorts(
    start: datetime = Query(...),
    end: datetime = Query(...),
    months: int = Query(6, ge=1, le=12),
    store: Store = Depends(get_owned_store),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(LTV_COHORTS_SQL, {"store_id": str(store.id), "start": start, "end": end, "months": months})
        .mappings()
        .all()
    )

    cohorts: dict = {}
    for row in rows:
        cohort = cohorts.setdefault(
            row["cohort_month"],
            {
                "cohort_month": row["cohort_month"],
                "new_customers": row["new_customers"],
                "cac": row["cac"],
                "by_month": {},
            },
        )
        if row["month_offset"] is not None:
            cohort["by_month"][row["month_offset"]] = float(row["avg_cumulative_ltv"] or 0)

    result = []
    for cohort in cohorts.values():
        ltv_by_month = []
        last = 0.0
        for offset in range(months):
            if offset in cohort["by_month"]:
                last = cohort["by_month"][offset]
            ltv_by_month.append(last)

        cac = cohort["cac"]
        payback_month = None
        if cac is not None:
            cac = float(cac)
            for offset, cumulative in enumerate(ltv_by_month):
                if cumulative >= cac:
                    payback_month = offset
                    break

        result.append(
            {
                "cohort_month": cohort["cohort_month"],
                "new_customers": cohort["new_customers"],
                "cac": cac,
                "ltv_by_month": ltv_by_month,
                "payback_month": payback_month,
            }
        )

    result.sort(key=lambda c: c["cohort_month"])
    return result
