-- CitationPulse schema snapshot (generated from SQLAlchemy models).
-- Authoritative evolution lives in Alembic migrations under infra/sql/alembic/versions.

-- Core entities:
-- tenants, memberships, brands, prompts, engine_runs, citations, alerts, alert_rules
-- phase3 entities: campaign_tasks, comms_logs, webhook_subscriptions

-- Vector extension:
CREATE EXTENSION IF NOT EXISTS vector;

