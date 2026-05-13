"""DataForSEO — Google Ads search volume (monthly estimates) with geo via ``location_code``.

Live endpoint docs:
  https://docs.dataforseo.com/v3/keywords_data/google_ads/search_volume/live/

``location_code`` — DataForSEO numeric geo id. Examples:
  2840  United States
  2036  Australia
  1003854  Sydney NSW   (see Keywords Data -> Google Ads -> Locations in their docs)

``language_code`` — ISO 639-1. e.g. ``en``, ``en-AU``.

``date_from`` / ``date_to`` — ``"YYYY-MM-DD"`` strings to request a specific month window.
  Omit both to get the last 12 months average.
  Example for April 2026: date_from="2026-04-01", date_to="2026-04-30"
"""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from citationpulse.core.config import Settings, get_settings

_log = logging.getLogger(__name__)

DATAFORSEO_SEARCH_VOLUME_URL = (
    "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live"
)


def dataforseo_configured(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return bool(s.dataforseo_login and s.dataforseo_password)


def _basic_auth_header(login: str, password: str) -> str:
    raw = f"{login}:{password}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


class DataForSEOError(RuntimeError):
    """Raised when DataForSEO returns an unexpected HTTP status or task error."""

    def __init__(self, message: str, status_code: int | None = None, raw: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.raw = raw


def fetch_google_ads_search_volumes(
    keywords: list[str],
    *,
    location_code: int,
    language_code: str = "en",
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Return keyword volume rows from DataForSEO Google Ads live endpoint.

    Each row includes:
      - ``keyword``          — the queried keyword
      - ``search_volume``    — average monthly searches (last 12 months)
      - ``competition``      — 0-1 advertiser competition score
      - ``cpc``              — average cost per click USD
      - ``monthly_searches`` — list of {year, month, search_volume} for each of the last 12 months

    To get a specific month's volume filter ``monthly_searches`` by year/month client-side
    (the live endpoint does not accept date_from / date_to).

    Raises ``DataForSEOError`` on HTTP / API-level errors so callers get a
    meaningful message instead of silent empty results.
    """
    s = settings or get_settings()
    if not dataforseo_configured(s):
        raise DataForSEOError(
            "DataForSEO is not configured — set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD "
            "in .env and restart the API."
        )

    # NOTE: Google Ads Search Volume Live does NOT support date_from/date_to filtering.
    # It always returns the last-12-months average in `search_volume` plus a
    # `search_volume_trend` array [{year, month, search_volume}, ...] for each month.
    # Callers should filter `search_volume_trend` client-side for a specific month.
    task: dict[str, Any] = {
        "keywords": keywords[:1000],
        "location_code": int(location_code),
        "language_code": language_code,
    }

    headers = {
        "Authorization": _basic_auth_header(s.dataforseo_login, s.dataforseo_password),
        "Content-Type": "application/json",
    }

    _log.debug(
        "DataForSEO search-volume: %d keywords, location=%s, lang=%s",
        len(keywords),
        location_code,
        language_code,
    )

    try:
        with httpx.Client(timeout=120.0) as client:
            r = client.post(DATAFORSEO_SEARCH_VOLUME_URL, headers=headers, json=[task])
    except httpx.RequestError as exc:
        raise DataForSEOError(f"Network error reaching DataForSEO: {exc}") from exc

    if r.status_code == 401:
        raise DataForSEOError(
            "DataForSEO returned 401 Unauthorised — check DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD.",
            status_code=401,
            raw=r.text[:500],
        )
    if r.status_code != 200:
        raise DataForSEOError(
            f"DataForSEO returned HTTP {r.status_code}.",
            status_code=r.status_code,
            raw=r.text[:500],
        )

    try:
        payload = r.json()
    except ValueError as exc:
        raise DataForSEOError("DataForSEO response is not valid JSON.", raw=r.text[:200]) from exc

    out: list[dict[str, Any]] = []
    errors: list[str] = []

    for t in payload.get("tasks") or []:
        task_status = t.get("status_code")
        if task_status and task_status != 20000:
            msg = t.get("status_message", "unknown task error")
            errors.append(f"Task error {task_status}: {msg}")
            continue
        for item in t.get("result") or []:
            if isinstance(item, list):
                for row in item:
                    if isinstance(row, dict):
                        out.append(row)
            elif isinstance(item, dict):
                out.append(item)

    if errors and not out:
        raise DataForSEOError("; ".join(errors))

    if errors:
        _log.warning("DataForSEO partial task errors: %s", "; ".join(errors))

    return out
