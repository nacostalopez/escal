from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StoreCreate(BaseModel):
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
    # CAPI feedback loop opt-in — see app/services/capi.py. capi_destination_id
    # is the Meta pixel id or Google conversionAction resource name.
    capi_enabled: bool = False
    capi_destination_id: str | None = None


class StoreCredentialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    store_id: UUID
    provider: str
    expires_at: datetime | None = None
    capi_enabled: bool = False
    capi_destination_id: str | None = None
