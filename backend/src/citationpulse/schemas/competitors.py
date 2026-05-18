from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from citationpulse.services.normalization import canonicalize_url, registrable_domain

CompetitorTypeInput = Literal["niche_specialist", "full_stack_niche"]
CitationType = Literal["homepage", "service_page", "about_page", "seo_evidence", "ranking"]


class CompetitorCitation(BaseModel):
    type: str
    url: str
    evidence: str


class TargetCompanyAnalysis(BaseModel):
    domain: str
    name: str
    detected_services: list[str] = Field(default_factory=list)
    detected_niche: str = ""
    detected_locations: list[str] = Field(default_factory=list)
    company_tier: str
    tier_reasoning: str


class SameLevelCompetitor(BaseModel):
    domain: str
    name: str
    tier: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    avg_position: float | None = None
    intersections: int | None = None
    reasoning: str
    citations: list[CompetitorCitation] = Field(default_factory=list)


class OneLevelAboveCompetitor(BaseModel):
    domain: str
    name: str
    tier: str
    authority_advantage: str
    reasoning: str
    citations: list[CompetitorCitation] = Field(default_factory=list)


class CompetitorDiscoveryResult(BaseModel):
    target_company: TargetCompanyAnalysis
    same_level_competitors: list[SameLevelCompetitor]
    one_level_above_competitors: list[OneLevelAboveCompetitor]


class CompetitorAnalyzeRequest(BaseModel):
    target_website: str = Field(..., min_length=3, max_length=2048)
    competitor_type: CompetitorTypeInput | None = None
    service: str | None = Field(None, max_length=512)
    niche: str | None = Field(None, max_length=512)
    location: str | None = Field(None, max_length=256)
    excluded_competitors: list[str] = Field(default_factory=list, max_length=50)
    market: str = Field(default="Australia", max_length=128)

    @field_validator("target_website")
    @classmethod
    def normalize_target(cls, v: str) -> str:
        raw = v.strip()
        if not raw:
            raise ValueError("target_website is required")
        url = raw if raw.startswith(("http://", "https://")) else f"https://{raw}"
        return canonicalize_url(url)

    @field_validator("excluded_competitors")
    @classmethod
    def normalize_excluded(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for item in v:
            dom = registrable_domain(
                item.strip() if item.strip().startswith("http") else f"https://{item.strip()}"
            )
            if not dom or dom in seen:
                continue
            seen.add(dom)
            out.append(dom)
        return out[:50]
