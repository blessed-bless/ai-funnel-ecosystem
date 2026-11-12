from datetime import datetime

from pydantic import BaseModel, Field


class LeadCreate(BaseModel):
    source: str = "direct"
    name: str | None = None
    phone: str | None = None
    telegram_id: str | None = None
    telegram_username: str | None = None
    need: str | None = None
    budget_note: str | None = None
    summary: str | None = None
    status: str = "new"


class LeadUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    need: str | None = None
    budget_note: str | None = None
    summary: str | None = None
    status: str | None = None
    telegram_username: str | None = None


class LeadOut(BaseModel):
    id: int
    source: str
    status: str
    name: str | None
    phone: str | None
    telegram_id: str | None
    telegram_username: str | None
    need: str | None
    budget_note: str | None
    summary: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChatIn(BaseModel):
    lead_id: int | None = None
    source: str = "direct"
    telegram_id: str | None = None
    telegram_username: str | None = None
    message: str = Field(min_length=1, max_length=4000)


class ChatOut(BaseModel):
    lead_id: int
    reply: str
    status: str
    ready_for_handoff: bool = False


class FunnelHitIn(BaseModel):
    source: str = "landing"
    utm_campaign: str | None = None
    path: str | None = None
