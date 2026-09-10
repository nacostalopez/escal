from datetime import date

from pydantic import BaseModel


class MetricsSummaryOut(BaseModel):
    revenue: float
    net_profit: float
    total_ad_spend: float
    real_profit_after_ads: float
    true_roas: float | None


class DailyMetricOut(BaseModel):
    day: date
    total_orders: int
    total_revenue: float
    total_cogs: float
    total_gateway_fees: float
    total_net_profit: float
    ad_spend: float


class CreativeMetricOut(BaseModel):
    platform: str
    ad_id: str
    ad_name: str | None
    campaign_name: str | None
    thumbnail_url: str | None
    spend: float
    impressions: int
    clicks: int
    # Percent (e.g. 2.35 = 2.35%), null with zero impressions.
    ctr: float | None
    cpc: float | None
    cpm: float | None


class CohortLtvOut(BaseModel):
    cohort_month: date
    new_customers: int
    # Blended spend / new_customers for the cohort's acquisition month; null
    # when there's no ad_spend data for that month.
    cac: float | None
    # Cumulative avg net profit per customer; index 0 = acquisition month.
    ltv_by_month: list[float]
    # First index where ltv_by_month >= cac; null if never (within the
    # window) or if cac itself is null.
    payback_month: int | None
