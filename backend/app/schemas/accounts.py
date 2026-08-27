from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AccountCreate(BaseModel):
    name: str


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_at: datetime | None = None
