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
