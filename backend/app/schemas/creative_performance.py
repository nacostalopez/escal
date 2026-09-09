from datetime import datetime

from pydantic import BaseModel


class CreativePerformanceCreate(BaseModel):
    time: datetime
    platform: str
    campaign_id: str
    campaign_name: str | None = None
    adset_id: str | None = None
    ad_id: str
    ad_name: str | None = None
    thumbnail_url: str | None = None
    spend: float
    impressions: int = 0
    clicks: int = 0
