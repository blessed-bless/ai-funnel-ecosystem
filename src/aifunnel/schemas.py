from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class LeadCreate(BaseModel):
    source: str = "direct"
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    telegram_id: str | None = None
    telegram_username: str | None = None
    need: str | None = None
    budget_note: str | None = None
    summary: str | None = None
    status: str = "new"
    funnel_id: int | None = None
    stage_slug: str | None = None
    score: int = 0

    @field_validator("source")
    @classmethod
    def _source_ok(cls, value: str) -> str:
        cleaned = value.strip()[:64]
        if not cleaned:
            raise ValueError("source пустой")
        return cleaned


class LeadUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    need: str | None = None
    budget_note: str | None = None
    summary: str | None = None
    status: str | None = None
    telegram_username: str | None = None
    funnel_id: int | None = None
    stage_slug: str | None = None
    score: int | None = None


class LeadOut(BaseModel):
    id: int
    source: str
    status: str
    funnel_id: int | None = None
    stage_slug: str | None = None
    name: str | None
    phone: str | None
    email: str | None = None
    telegram_id: str | None
    telegram_username: str | None
    need: str | None
    budget_note: str | None
    summary: str | None
    score: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChatIn(BaseModel):
    lead_id: int | None = None
    source: str = "direct"
    telegram_id: str | None = None
    telegram_username: str | None = None
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def _strip_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message пустой")
        return cleaned


class ChatOut(BaseModel):
    lead_id: int
    reply: str
    status: str
    ready_for_handoff: bool = False
    score: int = 0


class FunnelHitIn(BaseModel):
    source: str = "landing"
    utm_campaign: str | None = None
    path: str | None = None
    funnel_slug: str | None = "default"


class FunnelStageOut(BaseModel):
    id: int
    slug: str
    title: str
    position: int

    model_config = {"from_attributes": True}


class FunnelOut(BaseModel):
    id: int
    slug: str
    title: str
    description: str | None
    is_active: int
    stages: list[FunnelStageOut] = []

    model_config = {"from_attributes": True}


class FunnelCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=64)
    title: str = Field(min_length=2, max_length=160)
    description: str | None = None


class HealthOut(BaseModel):
    status: str
    version: str
    env: str


class ReadyOut(BaseModel):
    status: str
    database: str
    ai_circuit: str


class StatsOut(BaseModel):
    leads_total: int
    leads_ready: int
    leads_qualifying: int
    outbox_pending: int
