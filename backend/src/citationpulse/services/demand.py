"""Demand resolution — 4-step fallback that NEVER returns null / zero.

Pipeline (first step that yields a usable value wins):

    1. literal   DataForSEO Google Ads volume on the original prompt text.
                 Valid iff monthly volume >= MIN_VOLUME (default 50).

    2. variant   Decompose conversational prompts into 2–5 short keyword
                 variants ("cheapest way to hire a handyman in Sydney" →
                 ["handyman Sydney", "hire handyman", "handyman"]). Take
                 the highest successful volume.

    3. internal  Composite of three brand-side signals — answer richness,
                 engine consensus, and cross-tenant prompt similarity.
                 No external API call.

                     internal = 0.4 * richness + 0.3 * consensus + 0.3 * crowd

    4. default   Last-resort floor so the scorer always has a number:
                 ``demand_score = 0.30``, ``demand_bucket = "unknown"``.

All steps share the same return shape (``DemandResult``) so the scorer never
has to special-case which step produced the value.

DataForSEO lookups are cached in Redis for 7 days under ``df:vol:<variant>:<locale>``
(falls back to in-process cache when REDIS_URL is unset — see ``services.cache``).
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from citationpulse.models.domain import (
    Citation,
    EngineRun,
    Ownership,
    Prompt,
    RunStatus,
)
from citationpulse.services import cache
from citationpulse.services.dataforseo_keywords import (
    DataForSEOError,
    dataforseo_configured,
    fetch_google_ads_search_volumes,
)

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tuning knobs — kept as module constants so tests can monkeypatch them.
# Operators can override the volume thresholds in .env / Settings (see
# ``services.demand_settings_overrides`` below).
# ---------------------------------------------------------------------------
MIN_LITERAL_VOLUME = 50  # below this DataForSEO is treated as "no signal"
MIN_VARIANT_VOLUME = 50
CACHE_TTL_S = 7 * 24 * 3600  # 7 days
HIGH_VOLUME = 5000  # bucket threshold "high"
MEDIUM_VOLUME = 500  # bucket threshold "medium"
DEFAULT_DEMAND_SCORE = 0.30
DEFAULT_DEMAND_BUCKET = "unknown"


def _apply_settings_overrides() -> None:
    """Pull the bucket / threshold values from ``Settings`` if defined.

    Called lazily by ``resolve_demand`` so the import of this module is
    side-effect free (helps in tests + cold-start workers).
    """
    global MIN_LITERAL_VOLUME, MIN_VARIANT_VOLUME, HIGH_VOLUME, MEDIUM_VOLUME
    try:
        from citationpulse.core.config import get_settings

        s = get_settings()
        MIN_LITERAL_VOLUME = int(getattr(s, "demand_min_literal_volume", MIN_LITERAL_VOLUME))
        MIN_VARIANT_VOLUME = int(getattr(s, "demand_min_variant_volume", MIN_VARIANT_VOLUME))
        HIGH_VOLUME = int(getattr(s, "demand_high_volume", HIGH_VOLUME))
        MEDIUM_VOLUME = int(getattr(s, "demand_medium_volume", MEDIUM_VOLUME))
    except Exception:  # noqa: BLE001
        pass

# ---------------------------------------------------------------------------
# Locale → DataForSEO numeric location code. Kept aligned with
# ``services.opportunities._LOCALE_TO_LOCATION`` so a single ``opportunities``
# detector run uses one geo per prompt.
# ---------------------------------------------------------------------------
_LOCALE_TO_LOCATION: dict[str, int] = {
    "en-us": 2840,
    "en-au": 2036,
    "en-gb": 2826,
    "en-ca": 2124,
    "en-nz": 2554,
    "en-sg": 2702,
    "en-in": 2356,
    "en-za": 2710,
    "en-ie": 2372,
}
_DEFAULT_LOCATION_CODE = 2840


# ---------------------------------------------------------------------------
# English stop-words for variant decomposition. Small list on purpose: we only
# want to strip filler ("the", "for"), not topical words ("crm", "agency") or
# action verbs ("hire", "buy") — those drive the verb+tail variant.
# ---------------------------------------------------------------------------
_STOP = frozenset(
    """
    a an the and or but if then else for of in on at to from with by as is are was were be been being
    do does did doing have has had having i you he she it we they me him her us them my your his
    its our their this that these those what which who whom whose where when why how
    cheap cheapest best top good great new free near nearby around any all
    way ways need needs want wants looking look getting how-to
    """.split()
)

# Action verbs we keep in tokens but use as anchor points for the verb+tail variant.
_ACTION_VERBS = frozenset({"hire", "buy", "find", "compare", "switch", "rent", "use", "build"})


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class DemandResult:
    """Resolved demand for a single prompt.

    Attributes:
        score:        Normalised 0..1 demand value (input to the scorer).
        bucket:       Display pill — high | medium | low | unknown.
        source:       Which fallback step produced this value.
                      One of literal | variant | internal | default.
        variant:      The text actually used to obtain ``raw_volume`` (None
                      for ``internal`` / ``default``).
        raw_volume:   Monthly search volume from DataForSEO (None when source
                      is internal/default).
    """

    score: float
    bucket: str
    source: str
    variant: str | None
    raw_volume: int | None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Helpers — pure functions, all unit-testable.
# ---------------------------------------------------------------------------
_PUNCT = re.compile(r"[^\w\s\-]+")
_WS = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace.

    Used as the cache-key suffix and as the canonical form for DataForSEO.
    """
    if not text:
        return ""
    out = _PUNCT.sub(" ", text.lower())
    out = _WS.sub(" ", out).strip()
    return out


def bucket_from_volume(volume: int | None) -> str:
    """Map raw monthly volume to a display pill (high/medium/low).

    Thresholds are tuned for English-speaking SaaS markets; tweak in
    ``HIGH_VOLUME`` / ``MEDIUM_VOLUME`` if you serve a different niche.
    """
    if volume is None or volume <= 0:
        return "unknown"
    if volume >= HIGH_VOLUME:
        return "high"
    if volume >= MEDIUM_VOLUME:
        return "medium"
    return "low"


def score_from_volume(volume: int | None) -> float:
    """Log-scaled normalisation so a 50 000/mo prompt isn't 1000× a 50/mo one.

    Matches the existing scorer's ``log10(v)/5`` so existing rows stay
    comparable to literal-source scores.
    """
    v = max(int(volume or 1), 1)
    return min(math.log10(v) / 5.0, 1.0)


def decompose_prompt(text: str, *, max_variants: int = 5) -> list[str]:
    """Return 2–5 short keyword variants of a conversational prompt.

    Heuristic (deliberately cheap — no LLM call):
      1. Strip stop-words and short tokens.
      2. Pull out the noun-phrase trail (last 2–4 content words).
      3. Add bigrams and the single most-frequent content word as a fallback.

    Always returns the de-duplicated, non-empty result (may be shorter than
    ``max_variants`` for very short prompts). Order is stable so cache hits
    stay deterministic.
    """
    norm = normalise(text)
    if not norm:
        return []
    tokens = [t for t in norm.split() if t and t not in _STOP and len(t) > 1]
    if not tokens:
        return []

    seen: set[str] = set()
    out: list[str] = []

    def _push(variant: str) -> None:
        v = variant.strip()
        if not v or v in seen:
            return
        seen.add(v)
        out.append(v)

    # 1) full content-token phrase (e.g. "cheapest way to hire a handyman in Sydney" → "handyman sydney")
    _push(" ".join(tokens[-4:]) if len(tokens) >= 4 else " ".join(tokens))

    # 2) trailing bigram → "handyman sydney"
    if len(tokens) >= 2:
        _push(" ".join(tokens[-2:]))

    # 3) verb + topical-noun e.g. "hire handyman" — anchor the verb but jump
    # over filler so we don't end up with awkward "hire a" pairs.
    content_tokens = [t for t in tokens if t not in _ACTION_VERBS]
    for t in tokens:
        if t in _ACTION_VERBS and content_tokens:
            # Prefer the most-frequent content token (== "handyman" in the example).
            most_common = Counter(content_tokens).most_common(1)[0][0]
            _push(f"{t} {most_common}")
            break

    # 4) most-common content token → "handyman"
    common = Counter(tokens).most_common(1)
    if common:
        _push(common[0][0])

    # 5) leading bigram (fallback for queries like "best CRM for small business")
    if len(tokens) >= 2:
        _push(" ".join(tokens[:2]))

    return out[:max_variants]


# ---------------------------------------------------------------------------
# DataForSEO lookups (with Redis caching).
# ---------------------------------------------------------------------------
def _cache_key(variant: str, locale: str) -> str:
    """Stable cache key. Locale + normalised variant ensures Sydney vs US split."""
    return f"df:vol:{(locale or 'en-us').strip().lower()}:{normalise(variant)}"


def _location_for_locale(locale: str) -> tuple[int, str]:
    loc_lower = (locale or "en-US").lower().replace("_", "-")
    return (
        _LOCALE_TO_LOCATION.get(loc_lower, _DEFAULT_LOCATION_CODE),
        loc_lower.split("-")[0] or "en",
    )


def _lookup_volumes(
    keywords: list[str],
    *,
    locale: str,
    use_cache: bool = True,
) -> dict[str, int]:
    """Return {keyword_norm: monthly_volume}. Caches per (variant, locale) for 7 days.

    Skips the HTTP call when DataForSEO is not configured — caller treats
    "no signal" the same as "below threshold" and moves to the next step.
    """
    if not keywords:
        return {}

    norm_keywords = [normalise(k) for k in keywords if normalise(k)]
    if not norm_keywords:
        return {}

    out: dict[str, int] = {}
    misses: list[str] = []

    # 1) Try the cache first.
    if use_cache:
        for kw in norm_keywords:
            cached = cache.get_json(_cache_key(kw, locale))
            if cached is None:
                misses.append(kw)
                continue
            try:
                out[kw] = int(cached.get("volume", 0))
            except (AttributeError, TypeError, ValueError):
                misses.append(kw)
    else:
        misses = norm_keywords

    if not misses:
        return out

    # 2) Anything still missing → DataForSEO (if available).
    if not dataforseo_configured():
        # Cache "no data" briefly to avoid hammering an unconfigured deploy.
        # (Keys disappear after 1h so flipping the env flips on volumes promptly.)
        for kw in misses:
            cache.set_json(_cache_key(kw, locale), {"volume": 0}, ttl_s=3600)
        return out

    location_code, language_code = _location_for_locale(locale)
    try:
        rows = fetch_google_ads_search_volumes(
            misses,
            location_code=location_code,
            language_code=language_code,
        )
    except DataForSEOError as exc:
        _log.warning("demand: DataForSEO error locale=%s: %s", locale, exc)
        return out

    fetched: dict[str, int] = {}
    for row in rows:
        kw = normalise(str(row.get("keyword") or ""))
        sv = row.get("search_volume")
        if kw and isinstance(sv, (int, float)) and sv >= 0:
            fetched[kw] = int(sv)

    for kw in misses:
        vol = fetched.get(kw, 0)
        cache.set_json(_cache_key(kw, locale), {"volume": vol}, ttl_s=CACHE_TTL_S)
        out[kw] = vol

    return out


# ---------------------------------------------------------------------------
# Step 3 — internal composite (no external API).
# ---------------------------------------------------------------------------
def _answer_richness(db: Session, prompt_id: UUID) -> float:
    """Avg snippet length × log(citation count) on the prompt's latest runs.

    Idea: prompts that elicit long, citation-rich AI answers are usually
    high-demand — they map to information-rich SERPs.
    """
    since = datetime.now(timezone.utc) - timedelta(days=30)
    rows = list(
        db.scalars(
            select(EngineRun)
            .where(
                EngineRun.prompt_id == prompt_id,
                EngineRun.created_at >= since,
                EngineRun.status == RunStatus.OK.value,
            )
            .limit(10)
        ).all()
    )
    if not rows:
        return 0.0
    snippet_chars = 0
    citation_count = 0
    for r in rows:
        cites = list(db.scalars(select(Citation).where(Citation.engine_run_id == r.id)).all())
        citation_count += len(cites)
        snippet_chars += sum(len(c.snippet or "") for c in cites)
    if citation_count == 0:
        return 0.0
    avg_chars = snippet_chars / max(citation_count, 1)
    # Map both signals into [0, 1] with gentle log scaling.
    chars_norm = min(avg_chars / 600.0, 1.0)
    count_norm = min(math.log10(max(citation_count, 1) + 1) / 1.6, 1.0)
    return round(0.6 * chars_norm + 0.4 * count_norm, 4)


def _engine_consensus(db: Session, prompt_id: UUID) -> float:
    """Share of recent OK runs whose engines all produced citations.

    A prompt where every engine had something to say is a real demand signal
    — engines hallucinate less when corpus volume is high.
    """
    since = datetime.now(timezone.utc) - timedelta(days=30)
    runs = list(
        db.scalars(
            select(EngineRun)
            .where(
                EngineRun.prompt_id == prompt_id,
                EngineRun.created_at >= since,
                EngineRun.status == RunStatus.OK.value,
            )
            .limit(20)
        ).all()
    )
    if not runs:
        return 0.0
    with_cites = 0
    for r in runs:
        n = db.scalar(
            select(func.count())
            .select_from(Citation)
            .where(Citation.engine_run_id == r.id)
        )
        if int(n or 0) > 0:
            with_cites += 1
    return round(with_cites / float(len(runs)), 4)


def _crowd_similarity(db: Session, prompt: Prompt) -> float:
    """Cross-tenant prompt-text similarity. Tokens-in-common with the corpus.

    Implementation note: a true vector search needs pgvector + an index. To
    stay portable we approximate with token-overlap against a small recent
    sample of other tenants' prompts (max 200 rows).
    """
    my_tokens = {t for t in normalise(prompt.text or "").split() if t and t not in _STOP}
    if not my_tokens:
        return 0.0
    sample = list(
        db.scalars(
            select(Prompt.text)
            .where(Prompt.id != prompt.id)
            .order_by(Prompt.created_at.desc())
            .limit(200)
        ).all()
    )
    if not sample:
        return 0.0
    matches = 0
    for txt in sample:
        other = {t for t in normalise(txt or "").split() if t and t not in _STOP}
        if not other:
            continue
        overlap = len(my_tokens & other) / max(len(my_tokens | other), 1)
        if overlap >= 0.34:
            matches += 1
    return round(min(matches / 8.0, 1.0), 4)


def internal_demand_index(db: Session, prompt: Prompt) -> float:
    """Step 3 composite — never returns 0 if any sub-signal is non-zero.

    Weights match the spec: ``0.4 richness + 0.3 consensus + 0.3 crowd``.
    """
    richness = _answer_richness(db, prompt.id)
    consensus = _engine_consensus(db, prompt.id)
    crowd = _crowd_similarity(db, prompt)
    score = 0.4 * richness + 0.3 * consensus + 0.3 * crowd
    return round(float(min(max(score, 0.0), 1.0)), 4)


# ---------------------------------------------------------------------------
# Step 1+2 helpers
# ---------------------------------------------------------------------------
def _resolve_literal(prompt_text: str, locale: str) -> tuple[int, str] | None:
    """Step 1 — DataForSEO lookup with original prompt text.

    Returns (volume, normalised_variant) when volume meets the threshold,
    otherwise None (caller falls through to step 2).
    """
    norm = normalise(prompt_text)
    if not norm:
        return None
    vols = _lookup_volumes([norm], locale=locale)
    v = vols.get(norm, 0)
    if v >= MIN_LITERAL_VOLUME:
        return (v, norm)
    return None


def _resolve_variant(prompt_text: str, locale: str) -> tuple[int, str] | None:
    """Step 2 — try 2–5 decomposed variants, keep the highest above threshold."""
    variants = decompose_prompt(prompt_text)
    if not variants:
        return None
    vols = _lookup_volumes(variants, locale=locale)
    best: tuple[int, str] | None = None
    for v_norm in variants:  # iterate in stable order so ties pick the longest variant
        v = vols.get(normalise(v_norm), 0)
        if v < MIN_VARIANT_VOLUME:
            continue
        if best is None or v > best[0]:
            best = (v, v_norm)
    return best


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def resolve_demand(
    db: Session,
    prompt: Prompt,
    *,
    locale: str | None = None,
) -> DemandResult:
    """Run the 4-step fallback and return a guaranteed-non-null DemandResult.

    Does NOT persist — see ``persist_demand_to_prompt`` for the side effect.
    Separating the two makes it trivial to unit-test the scoring logic
    without touching the DB session.
    """
    _apply_settings_overrides()
    loc = (locale or prompt.locale or "en-US").strip() or "en-US"

    # Step 1
    literal = _resolve_literal(prompt.text or "", loc)
    if literal is not None:
        vol, variant = literal
        return DemandResult(
            score=score_from_volume(vol),
            bucket=bucket_from_volume(vol),
            source="literal",
            variant=variant,
            raw_volume=vol,
        )

    # Step 2
    variant_hit = _resolve_variant(prompt.text or "", loc)
    if variant_hit is not None:
        vol, variant = variant_hit
        return DemandResult(
            score=score_from_volume(vol),
            bucket=bucket_from_volume(vol),
            source="variant",
            variant=variant,
            raw_volume=vol,
        )

    # Step 3 — internal composite (no external lookup).
    internal_score = internal_demand_index(db, prompt)
    if internal_score > 0:
        # Map internal [0,1] → a virtual "bucket" so the UI pill is sensible.
        # Reuse the volume thresholds via inverse log to keep one rule of thumb.
        virtual_volume = int(round(10 ** (internal_score * 5.0)))
        return DemandResult(
            score=internal_score,
            bucket=bucket_from_volume(virtual_volume),
            source="internal",
            variant=None,
            raw_volume=None,
        )

    # Step 4 — hard floor.
    return DemandResult(
        score=DEFAULT_DEMAND_SCORE,
        bucket=DEFAULT_DEMAND_BUCKET,
        source="default",
        variant=None,
        raw_volume=None,
    )


def persist_demand_to_prompt(prompt: Prompt, result: DemandResult) -> None:
    """Write the resolved demand back onto the ORM instance (caller commits)."""
    prompt.demand_score = float(result.score)
    prompt.demand_bucket = result.bucket
    prompt.demand_source = result.source
    prompt.demand_variant = result.variant
    prompt.demand_raw_volume = result.raw_volume
    prompt.demand_refreshed_at = datetime.now(timezone.utc)


def stale_prompt_ids(db: Session, *, max_age_days: int = 7) -> list[UUID]:
    """IDs of enabled prompts whose demand has never been computed or is stale.

    Used by the weekly ``refresh_demand`` Celery task. Returns at most
    ``Prompt`` rows; callers should batch through them.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    stmt = select(Prompt.id).where(
        Prompt.enabled.is_(True),
        (Prompt.demand_refreshed_at.is_(None)) | (Prompt.demand_refreshed_at < cutoff),
    )
    return list(db.scalars(stmt).all())


def refresh_demand_for_prompts(
    db: Session,
    prompt_ids: Iterable[UUID],
    *,
    locale_override: str | None = None,
) -> int:
    """Refresh demand for the given prompt ids, commit once, return count."""
    updated = 0
    for pid in prompt_ids:
        p = db.get(Prompt, pid)
        if not p or not p.enabled:
            continue
        result = resolve_demand(db, p, locale=locale_override)
        persist_demand_to_prompt(p, result)
        updated += 1
    if updated:
        db.commit()
    return updated


__all__ = [
    "DemandResult",
    "MIN_LITERAL_VOLUME",
    "MIN_VARIANT_VOLUME",
    "HIGH_VOLUME",
    "MEDIUM_VOLUME",
    "DEFAULT_DEMAND_SCORE",
    "DEFAULT_DEMAND_BUCKET",
    "normalise",
    "decompose_prompt",
    "bucket_from_volume",
    "score_from_volume",
    "internal_demand_index",
    "resolve_demand",
    "persist_demand_to_prompt",
    "stale_prompt_ids",
    "refresh_demand_for_prompts",
]
