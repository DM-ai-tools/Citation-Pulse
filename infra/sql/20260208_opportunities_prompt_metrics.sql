-- Top Gap Opportunities + prompt search volume (run once against Postgres).
-- Safe to re-run: uses IF NOT EXISTS where applicable.

ALTER TABLE prompts
  ADD COLUMN IF NOT EXISTS consecutive_gap_runs integer NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS prompt_metrics (
  prompt_id uuid PRIMARY KEY REFERENCES prompts(id) ON DELETE CASCADE,
  est_volume integer NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS opportunities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_id uuid NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
  prompt_id uuid NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
  gap_type text NOT NULL,
  scope text NOT NULL DEFAULT '',
  grade text NOT NULL,
  opportunity_score numeric(6,4) NOT NULL,
  description text NOT NULL,
  est_volume integer NULL,
  detected_at timestamptz NOT NULL DEFAULT now(),
  status text NOT NULL DEFAULT 'open',
  CONSTRAINT ck_opportunity_grade CHECK (grade IN ('A','B','C')),
  CONSTRAINT ck_opportunity_status CHECK (status IN ('open','snoozed','queued','resolved')),
  CONSTRAINT uq_opportunity_brand_prompt_gap_scope UNIQUE (brand_id, prompt_id, gap_type, scope)
);

CREATE INDEX IF NOT EXISTS ix_opportunities_brand_status_score
  ON opportunities (brand_id, status, opportunity_score DESC);
