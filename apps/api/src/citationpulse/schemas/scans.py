from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from citationpulse.services.normalization import ensure_https_url, registrable_domain


class ScanCreate(BaseModel):
    url: str = Field(..., min_length=3, max_length=2048)
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

    @model_validator(mode="before")
    @classmethod
    def force_auto_discover(cls, data: object) -> object:
        if isinstance(data, dict):
            data = dict(data)
            data["auto_discover_competitors"] = True
        return data

    @field_validator("prompts")
    @classmethod
    def strip_prompts(cls, v: list[str]) -> list[str]:
        out = [p.strip() for p in v if p.strip()]
        if not out:
            raise ValueError("At least one non-empty prompt is required")
        return out[:8]

    @field_validator("url")
    @classmethod
    def normalize_website_url(cls, v: str) -> str:
        url = ensure_https_url(v)
        if not url or not registrable_domain(url):
            raise ValueError("Enter a valid website or domain (e.g. hipages.com.au)")
        return url

    @field_validator("competitors")
    @classmethod
    def cap_competitors(cls, v: list[str]) -> list[str]:
        return [c.strip() for c in v if c.strip()][:5]


class ScanCreateResponse(BaseModel):
    scan_id: str


class ShareBody(BaseModel):
    share_public: bool = True
