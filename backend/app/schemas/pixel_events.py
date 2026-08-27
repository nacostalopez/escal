from datetime import datetime

from pydantic import BaseModel


class PixelEventCreate(BaseModel):
    time: datetime
    event_name: str
    event_id: str | None = None
    anonymous_id: str | None = None
    user_email_hash: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
