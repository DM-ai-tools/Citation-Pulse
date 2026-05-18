from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ScanCreate(BaseModel):
    url: HttpUrl
    competitors: Annotated[list[str], Field(default_factory=list, max_length=5)]
    prompts: Annotated[list[str], Field(min_length=1, max_length=8)]
    locale: str = Field(default="en-US", max_length=32)
    engines: list[str] | None = None
    auto_discover_competitors: bool = True
    competitor_type: str | None = Field(None, max_length=64)
    service: str | None = Field(None, max_length=512)
    niche: str | None = Field(None, max_length=512)
    location: str | None = Field(None, max_length=256)
    excluded_competitors: Annotated[list[str], Field(default_factory=list, max_length=50)]

    @field_validator("prompts")
    @classmethod
    def strip_prompts(cls, v: list[str]) -> list[str]:
        out = [p.strip() for p in v if p.strip()]
        if not out:
            raise ValueError("At least one non-empty prompt is required")
        return out[:8]

    @field_validator("competitors")
    @classmethod
    def cap_competitors(cls, v: list[str]) -> list[str]:
        return [c.strip() for c in v if c.strip()][:5]


class ScanCreateResponse(BaseModel):
    scan_id: str


class ShareBody(BaseModel):
    share_public: bool = True
