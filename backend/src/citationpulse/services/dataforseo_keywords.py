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
import re
import unicodedata
from typing import Any

import httpx

from citationpulse.core.config import Settings, get_settings

_log = logging.getLogger(__name__)

DATAFORSEO_SEARCH_VOLUME_URL = (
    "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live"
)

# Google Ads search-volume live — https://docs.dataforseo.com/v3/keywords_data/google_ads/search_volume/live/
DATAFORSEO_MAX_KEYWORD_CHARS = 80
DATAFORSEO_MAX_KEYWORD_WORDS = 10
_INVALID_KW_CHARS = re.compile(r"[?!;:\"'()[\]{}<>@#$%^&*\\|~`]")
_DOMAIN_RE = re.compile(
    r"\b[\w][\w-]*\.(?:com|net|org|io|co|au)(?:\.[a-z]{2})?\b",
    re.IGNORECASE,
)
_COMPARE_PREFIX_RE = re.compile(
    r"^\s*(?:compare|comparison|versus|vs\.?|between)\b\s*",
    re.IGNORECASE,
)


def _to_ascii_keyword_text(text: str) -> str:
    """Google Ads keywords reject many Unicode symbols (smart quotes, em dashes, etc.)."""
    s = (text or "").replace("\ufffd", " ")
    for src, dst in (
        ("\u2018", "'"),
        ("\u2019", "'"),
        ("\u201c", '"'),
        ("\u201d", '"'),
        ("\u2013", "-"),
        ("\u2014", "-"),
        ("\u2026", " "),
        ("\u00a0", " "),
    ):
        s = s.replace(src, dst)
    normalized = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in normalized if ord(ch) < 128)


def normalize_keyword_for_dataforseo(text: str) -> str:
    """Fit a scan prompt or phrase to Google Ads keyword limits (80 chars, 10 words)."""
    cleaned = _to_ascii_keyword_text(text)
    cleaned = _INVALID_KW_CHARS.sub(" ", cleaned)
    cleaned = cleaned.strip(" '\"`")
    words = cleaned.split()
    words = [w.strip("'\"`") for w in words if w.strip("'\"`.")]
    if len(words) > DATAFORSEO_MAX_KEYWORD_WORDS:
        words = words[:DATAFORSEO_MAX_KEYWORD_WORDS]
    kw = " ".join(words)
    if len(kw) <= DATAFORSEO_MAX_KEYWORD_CHARS:
        return kw
    out: list[str] = []
    length = 0
    for word in words:
        add = len(word) + (1 if out else 0)
        if length + add > DATAFORSEO_MAX_KEYWORD_CHARS:
            break
        out.append(word)
        length += add
    if not out and words:
        return words[0][:DATAFORSEO_MAX_KEYWORD_CHARS].strip()
    return " ".join(out).strip()


def search_volume_from_row(row: dict[str, Any]) -> int | None:
    """Parse monthly search volume from a DataForSEO keyword row."""
    sv = row.get("search_volume")
    if isinstance(sv, (int, float)) and sv >= 0:
        return int(sv)
    monthly = row.get("monthly_searches")
    if isinstance(monthly, list):
        vals = [
            int(m.get("search_volume"))
            for m in monthly
            if isinstance(m, dict)
            and isinstance(m.get("search_volume"), (int, float))
            and m.get("search_volume", -1) >= 0
        ]
        if vals:
            return int(sum(vals) / len(vals))
    return None


def extract_volume_keyword_candidates(prompt_text: str, *, max_candidates: int = 6) -> list[str]:
    """Build short Google-Ads-style phrases when the full scan prompt has no volume data."""
    raw = (prompt_text or "").strip()
    if not raw:
        return []

    candidates: list[str] = []
    seen: set[str] = set()

    def add(phrase: str) -> None:
        kw = normalize_keyword_for_dataforseo(phrase)
        key = kw.lower()
        if kw and key not in seen:
            seen.add(key)
            candidates.append(kw)

    add(raw)
    stripped = _COMPARE_PREFIX_RE.sub("", raw)
    stripped = _DOMAIN_RE.sub(" ", stripped)
    stripped = re.sub(r"\b(?:and|or|the|best|top|leading)\b", " ", stripped, flags=re.IGNORECASE)
    stripped = " ".join(stripped.split())
    if stripped and stripped.lower() != raw.lower():
        add(stripped)

    for m in re.finditer(
        r"\b(?:for|in)\s+([A-Za-z][\w\s'-]{2,48})",
        stripped,
        flags=re.IGNORECASE,
    ):
        add(m.group(1).strip())

    loc_m = re.search(r"\bin\s+([A-Za-z][A-Za-z\s'-]{2,32})\s*$", stripped, flags=re.IGNORECASE)
    if loc_m:
        loc = loc_m.group(1).strip()
        head = re.split(r"\b(?:for|in)\b", stripped, maxsplit=1, flags=re.IGNORECASE)[0]
        head = " ".join(_DOMAIN_RE.sub(" ", head).split())
        head = re.sub(r"\b(?:quotes?|services?|providers?)\b", "", head, flags=re.IGNORECASE)
        head = " ".join(head.split())
        if head:
            add(f"{head} {loc}")
        add(f"home renovation {loc}")

    words = stripped.split()
    if len(words) >= 3:
        add(" ".join(words[-5:]))
        add(" ".join(words[-3:]))

    return candidates[:max_candidates]


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
    """Return keyword volume rows from DataForSEO Google Ads live endpoint."""
    s = settings or get_settings()
    if not dataforseo_configured(s):
        raise DataForSEOError(
            "DataForSEO is not configured — set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD "
            "in .env and restart the API."
        )

    api_keywords: list[str] = []
    seen: set[str] = set()
    for raw in keywords[:1000]:
        kw = normalize_keyword_for_dataforseo(raw)
        if not kw:
            continue
        key = kw.lower()
        if key in seen:
            continue
        seen.add(key)
        api_keywords.append(kw)

    if not api_keywords:
        return []

    task: dict[str, Any] = {
        "keywords": api_keywords,
        "location_code": int(location_code),
        "language_code": language_code,
    }

    headers = {
        "Authorization": _basic_auth_header(s.dataforseo_login, s.dataforseo_password),
        "Content-Type": "application/json",
    }

    _log.debug(
        "DataForSEO search-volume: %d keywords, location=%s, lang=%s",
        len(api_keywords),
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
        if any("40501" in e or "Invalid Field" in e for e in errors) and len(api_keywords) > 1:
            safe = [kw for kw in api_keywords if kw == normalize_keyword_for_dataforseo(kw)]
            safe = list(dict.fromkeys(safe))
            if safe and safe != api_keywords:
                _log.warning(
                    "DataForSEO keyword batch rejected; retrying with %d/%d sanitized keywords",
                    len(safe),
                    len(api_keywords),
                )
                return fetch_google_ads_search_volumes(
                    safe,
                    location_code=location_code,
                    language_code=language_code,
                    settings=s,
                )
        raise DataForSEOError("; ".join(errors))

    if errors:
        _log.warning("DataForSEO partial task errors: %s", "; ".join(errors))

    return out
