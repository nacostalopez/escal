from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StoreCreate(BaseModel):
    account_id: UUID
    name: str
    platform: str
    currency: str = "USD"
    timezone: str = "UTC"


class StoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    name: str
    platform: str
    currency: str
    timezone: str
    created_at: datetime | None = None


class StoreCredentialCreate(BaseModel):
    provider: str
    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None


class StoreCredentialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    store_id: UUID
    provider: str
    expires_at: datetime | None = None
