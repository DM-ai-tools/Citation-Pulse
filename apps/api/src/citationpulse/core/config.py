from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
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

    # --- Unified LLM gateway (OpenRouter) ---
    # ALL provider calls (ChatGPT, Claude, Gemini, Perplexity) are now routed
    # through OpenRouter with a single key. Get one at https://openrouter.ai/keys.
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

    # --- Legacy provider keys (kept for back-compat / migration only) ---
    # If `openrouter_api_key` is set, these are IGNORED. They remain here so an
    # operator can still flip back to direct-SDK mode by deleting their
    # OPENROUTER_API_KEY without losing their previous setup.
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
    claude_model: str = "anthropic/claude-3.5-haiku:online"
    gemini_model: str = "google/gemini-2.0-flash-001:online"
    perplexity_model: str = "perplexity/sonar"

    # Sentiment classifier — uses a cheap fast model. Same OpenRouter slug
    # convention. No `:online` because we don't need web search for sentiment.
    sentiment_model: str = "anthropic/claude-3.5-haiku"

    # Per-call tunables for the LLM router.
    llm_request_timeout_s: float = 120.0
    llm_max_retries: int = 3
    llm_max_tokens: int = 1024

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

    # Public API (Phase 3) — optional HMAC
    public_api_hmac_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _to_sqla_url(database_url: str) -> str:
    """Map a SQLAlchemy psycopg URL to the form Celery's SQLAlchemy transport expects."""
    return database_url


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
