from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BrandCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=512)
    domains: list[str] = Field(default_factory=list)
    competitor_brand_ids: list[uuid.UUID] = Field(default_factory=list, description="Other brand UUIDs")


class BrandRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    domains: list[str]
    competitors: list[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}


class PromptCreate(BaseModel):
    text: str
    locale: str = "en-US"
    intent: str | None = None
    enabled: bool = True


class PromptBulkCreate(BaseModel):
    prompts: list[PromptCreate]


class PromptRead(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    text: str
    locale: str
    intent: str | None
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RunCreate(BaseModel):
    """Ad-hoc run: optional subset of engines; default all API engines."""

    engines: list[str] | None = None


class RunRead(BaseModel):
    id: uuid.UUID
    prompt_id: uuid.UUID
    engine: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    cost_usd: str | None = None

    model_config = {"from_attributes": True}


class CitationRead(BaseModel):
    id: uuid.UUID
    engine_run_id: uuid.UUID
    url: str
    domain: str
    position: int | None
    snippet: str | None
    ownership: str
    sentiment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SoVRead(BaseModel):
    brand_id: uuid.UUID
    range_days: int
    brand_share: float
    competitor_share: float
    third_party_share: float
    neutral_share: float


class GapRead(BaseModel):
    prompt_id: uuid.UUID
    score: float
    reason: str


class OpportunityRead(BaseModel):
    """One row in the Top Gap Opportunities table.

    The ``demand_*`` fields surface the precomputed demand signal so the UI
    can render the HIGH/MEDIUM/LOW pill (``demand_bucket``) and the tooltip
    (raw volume + which step in the 4-step fallback produced the value).

    Per spec: ``demand_raw_volume`` is NOT shown in the row directly — UIs
    only render it inside the tooltip / details drawer.
    """

    id: uuid.UUID
    brand_id: uuid.UUID
    prompt_id: uuid.UUID
    title: str
    gap_type: str
    scope: str | None = None
    grade: str
    heat: str  # HOT | WARM | COOL — derived from grade
    opportunity_score: float
    description: str
    est_volume: int | None
    status: str
    detected_at: datetime

    # --- Demand signal (precomputed) ---
    demand_score: float | None = None
    demand_bucket: str | None = None  # high | medium | low | unknown
    demand_pill: str | None = None  # HIGH | MEDIUM | LOW | UNKNOWN
    demand_source: str | None = None  # literal | variant | internal | default
    demand_variant: str | None = None  # the variant that gave us the volume
    demand_raw_volume: int | None = None  # tooltip / details only
    demand_refreshed_at: datetime | None = None

    model_config = {"from_attributes": False}


class OpportunityListResponse(BaseModel):
    """Envelope for paginated opportunity listings.

    The frontend can ignore the envelope and read ``items`` for the simple
    case — but pagination metadata is here for table virtualisation.
    """

    items: list[OpportunityRead]
    total: int
    limit: int
    offset: int
    has_more: bool


class AlertRuleCreate(BaseModel):
    brand_id: uuid.UUID | None = None
    rule: str
    config: dict = Field(default_factory=dict)
    channel: str = "slack"


class AlertRuleRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    brand_id: uuid.UUID | None
    rule: str
    config: dict
    channel: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertFeedItem(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    rule: str
    payload: dict
    fired_at: datetime
    channel: str

    model_config = {"from_attributes": True}
