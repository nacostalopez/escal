from datetime import datetime

from pydantic import BaseModel


class AdSpendCreate(BaseModel):
    time: datetime
    platform: str
    campaign_id: str
    campaign_name: str | None = None
    adset_id: str | None = None
    spend: float
    impressions: int = 0
    clicks: int = 0
