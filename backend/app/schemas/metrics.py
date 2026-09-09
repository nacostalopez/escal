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
