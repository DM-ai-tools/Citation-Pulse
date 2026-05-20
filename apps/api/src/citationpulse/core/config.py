from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from citationpulse.db.urls import normalize_database_url

# apps/api/src/citationpulse/core/config.py → repo root is parents[5]
_REPO_ROOT = Path(__file__).resolve().parents[5]
_API_ROOT = Path(__file__).resolve().parents[3]


def _settings_env_files() -> tuple[str, ...]:
    """Absolute paths so uvicorn cwd (apps/api) still loads the monorepo .env."""
    out: list[str] = []
    for p in (_REPO_ROOT / ".env", _API_ROOT / ".env", Path(".env")):
        if p.is_file():
            out.append(str(p))
    return tuple(out)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_settings_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = "postgresql+psycopg://citationpulse:citationpulse@localhost:5434/citationpulse_geo"

    # Postgres-backed Celery (no Redis required). Defaults derive from `database_url` at runtime
    # via `effective_celery_broker_url` / `effective_celery_result_backend`.
    celery_broker_url: str = ""
    celery_result_backend: str = ""

    # SSE polling interval for live scan stream (seconds). Tradeoff: lower = snappier UI,
    # higher = less DB load. 0.5–1.0s is a fine sweet spot for dev.
    sse_poll_interval_s: float = 0.6
    sse_keepalive_interval_s: float = 15.0

    # Phase 1: no Clerk required when unset + development
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    clerk_audience: str = ""
    internal_phase1: bool = True
    internal_api_key: str = ""

    # Native email/password auth (Citation Pulse accounts)
    auth_jwt_secret: str = "change-me-set-AUTH_JWT_SECRET-in-production"
    auth_jwt_expire_hours: int = 72
    auth_admin_name: str = "Administrator"
    auth_admin_email: str = ""
    auth_admin_password: str = ""

    api_cors_origins: str = "http://localhost:3000"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    sentry_dsn: str = ""
    otel_exporter_otlp_endpoint: str = ""
    log_level: str = "info"

    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_raw_payloads: str = ""
    r2_public_base_url: str = ""

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_saas: str = ""  # $597/mo price id
    stripe_price_dfy: str = ""  # $1200/mo price id

    # Hybrid routing: ChatGPT/Claude use direct keys when set; Gemini/Perplexity use OpenRouter.
    # Set CLAUDE_PREFER_OPENROUTER=true to skip Anthropic direct (e.g. when direct credits are exhausted).
    claude_prefer_openrouter: bool = False
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Optional OpenRouter analytics headers — appear on the public leaderboard
    # if app title is set, but are otherwise harmless.
    openrouter_http_referer: str = "https://citationpulse.local"
    openrouter_app_title: str = "CitationPulse GEO"

    @field_validator("openrouter_api_key", mode="before")
    @classmethod
    def normalise_openrouter_api_key(cls, v: object) -> str:
        """Strip whitespace / accidental wrapping quotes so Railway .env typos don't yield HTTP 401."""
        if v is None:
            return ""
        s = str(v).strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
            s = s[1:-1].strip()
        return s

    @field_validator("openai_api_key", "anthropic_api_key", mode="before")
    @classmethod
    def normalise_provider_api_keys(cls, v: object) -> str:
        if v is None:
            return ""
        s = str(v).strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
            s = s[1:-1].strip()
        return s

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_ai_api_key: str = ""
    perplexity_api_key: str = ""
    chatgpt_session_token: str = ""
    playwright_proxy_server: str = ""

    # Engine model slugs. When OpenRouter is in use these are OpenRouter
    # model identifiers ("<provider>/<model>"). The `:online` suffix enables
    # OpenRouter's web-search plugin for citation grounding on models that
    # don't have native web search (ChatGPT / Claude / Gemini). Perplexity's
    # `sonar` already has native web search, so no `:online` suffix.
    chatgpt_model: str = "openai/gpt-4o-mini:online"
    claude_model: str = "anthropic/claude-sonnet-4:online"
    gemini_model: str = "google/gemini-2.0-flash-001:online"
    perplexity_model: str = "perplexity/sonar"
    openai_direct_model: str = "gpt-4o-mini-search-preview"
    anthropic_direct_model: str = "claude-sonnet-4-5-20250929"

    # Sentiment classifier — uses a cheap fast model. Same OpenRouter slug
    # convention. No `:online` because we don't need web search for sentiment.
    sentiment_model: str = "anthropic/claude-3.5-haiku"

    # Per-call tunables for the LLM router.
    llm_request_timeout_s: float = 120.0
    llm_max_retries: int = 3
    llm_max_tokens: int = 1024

    # Competitor discovery (POST /api/v1/competitors/analyze) — web-grounded JSON via OpenRouter.
    competitor_discovery_model: str = "perplexity/sonar"
    competitor_discovery_max_tokens: int = 8192
    competitor_analyze_rate_limit_per_hour: int = 12
    competitor_analyze_mesh_rate_limit_per_hour: int = 120

    # --- Legacy model-override aliases (kept so old .env files keep working) ---
    # If set, these override the OpenRouter slugs above. Empty by default.
    openai_model: str = ""
    anthropic_model: str = ""
    google_ai_model: str = ""
    anthropic_sentiment_model: str = ""

    # Alerts
    slack_webhook_url: str = ""
    resend_api_key: str = ""
    alerts_from_email: str = "alerts@citationpulse.local"

    # Canary
    canary_brand_id: str = ""

    # Gap / scoring
    gap_absence_run_threshold: int = 3

    # Anonymous POST /api/v1/scans — per resolved client IP per hour. Railway needs
    # correct X-Forwarded-For handling (see Dockerfile / FORWARDED_ALLOW_IPS). Set
    # ANONYMOUS_SCAN_RATE_LIMIT_PER_HOUR=0 to disable (not recommended on public URLs).
    anonymous_scan_rate_limit_per_hour: int = 24

    # When the TCP peer is still Railway CGNAT (100.64/10) or we cannot resolve a public
    # client IP, many users would share one bucket. Use a synthetic key with this higher cap.
    anonymous_scan_mesh_rate_limit_per_hour: int = 400

    # Public API (Phase 3) — optional HMAC
    public_api_hmac_secret: str = ""

    # --- DataForSEO (optional) — Google Ads monthly search volumes by geo ---
    # https://docs.dataforseo.com/v3/keywords_data/google_ads/search_volume/live/
    dataforseo_login: str = ""
    dataforseo_password: str = ""

    @field_validator("dataforseo_password", "dataforseo_login", mode="before")
    @classmethod
    def normalise_dataforseo_secrets(cls, v: object) -> str:
        if v is None:
            return ""
        s = str(v).strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
            s = s[1:-1].strip()
        return s

    @field_validator("database_url", mode="before")
    @classmethod
    def normalise_database_url(cls, v: object) -> str:
        """Railway Postgres often provides ``postgresql://``; SQLAlchemy needs ``postgresql+psycopg://``."""
        if v is None:
            return ""
        return normalize_database_url(str(v))


_WEAK_JWT_SECRETS = frozenset(
    {
        "",
        "change-me-set-AUTH_JWT_SECRET-in-production",
        "change-me-use-openssl-rand-hex-32",
    }
)


def validate_production_settings(s: Settings | None = None) -> None:
    """Fail fast when production is misconfigured (Railway deploy safety)."""
    s = s or get_settings()
    if s.environment.lower() != "production":
        return
    secret = (s.auth_jwt_secret or "").strip()
    if secret in _WEAK_JWT_SECRETS or len(secret) < 32:
        raise RuntimeError(
            "AUTH_JWT_SECRET must be set to a strong random value (32+ chars) when ENVIRONMENT=production"
        )
    if s.internal_phase1 and not (s.clerk_jwks_url or "").strip():
        _log = __import__("logging").getLogger(__name__)
        _log.warning(
            "INTERNAL_PHASE1=true in production without Clerk — ensure native auth is intended."
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _to_sqla_url(database_url: str) -> str:
    """Map a SQLAlchemy psycopg URL to the form Celery's SQLAlchemy transport expects."""
    return normalize_database_url(database_url)


def effective_celery_broker_url(s: Settings | None = None) -> str:
    s = s or get_settings()
    if s.celery_broker_url:
        return s.celery_broker_url
    return f"sqla+{_to_sqla_url(s.database_url)}"


def effective_celery_result_backend(s: Settings | None = None) -> str:
    s = s or get_settings()
    if s.celery_result_backend:
        return s.celery_result_backend
    return f"db+{_to_sqla_url(s.database_url)}"


def _is_railway_deploy() -> bool:
    """True when the process runs on Railway (any service in the project)."""
    return any(
        os.environ.get(k)
        for k in (
            "RAILWAY_ENVIRONMENT",
            "RAILWAY_ENVIRONMENT_NAME",
            "RAILWAY_PROJECT_ID",
            "RAILWAY_SERVICE_ID",
            "RAILWAY_SERVICE_NAME",
        )
    )


def celery_run_tasks_inline(s: Settings | None = None) -> bool:
    """Run Celery tasks in-process (``task_always_eager``) instead of a worker consumer.

    Local dev defaults to inline so scans work without ``celery worker``.
    On Railway, inline is enabled unless ``CELERY_USE_WORKER=1`` (separate worker service).
    """
    s = s or get_settings()
    eager_env = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "").strip().lower()
    use_worker = os.environ.get("CELERY_USE_WORKER", "").strip().lower() in ("1", "true", "yes")
    if eager_env in ("1", "true", "yes"):
        return True
    if eager_env in ("0", "false", "no"):
        return False
    if use_worker:
        return False
    if s.environment.lower() in ("development", "dev", "local"):
        return True
    if _is_railway_deploy():
        return True
    return False
