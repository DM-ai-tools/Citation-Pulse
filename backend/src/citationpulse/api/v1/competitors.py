from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status

from citationpulse.core.config import get_settings
from citationpulse.schemas.competitors import CompetitorAnalyzeRequest, CompetitorDiscoveryResult
from citationpulse.services.client_ip import effective_client_ip, is_mesh_or_unresolved_client_ip
from citationpulse.services.competitor_discovery import CompetitorDiscoveryError, analyze_competitors
from citationpulse.services.rate_limit import allow_competitor_analyze

router = APIRouter(prefix="/competitors", tags=["competitors"])
_log = logging.getLogger(__name__)


@router.post(
    "/analyze",
    response_model=CompetitorDiscoveryResult,
    status_code=status.HTTP_200_OK,
    summary="Discover Australian-market competitors (JSON)",
)
def analyze_competitors_endpoint(
    request: Request,
    body: CompetitorAnalyzeRequest,
) -> CompetitorDiscoveryResult:
    """Run competitive-intelligence discovery for a target website.

    Uses OpenRouter with web search. Returns exactly 3 same-level and 3
    one-level-above competitors with citations, or HTTP 422/503 on failure.
    """
    settings = get_settings()
    ip = effective_client_ip(request)
    rl_key = ip
    rl_limit = settings.competitor_analyze_rate_limit_per_hour
    if is_mesh_or_unresolved_client_ip(ip):
        rl_key = "__platform_mesh__"
        rl_limit = settings.competitor_analyze_mesh_rate_limit_per_hour
    if not allow_competitor_analyze(rl_key, limit_per_hour=rl_limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many competitor analyses — try again later",
        )

    try:
        return analyze_competitors(body)
    except CompetitorDiscoveryError as exc:
        msg = str(exc)
        if "OPENROUTER" in msg.upper() or "not configured" in msg.lower():
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg) from exc
    except Exception as exc:
        _log.exception("competitor analyze failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Competitor analysis failed",
        ) from exc
